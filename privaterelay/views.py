from datetime import datetime, timedelta, timezone
from functools import lru_cache
from hashlib import sha256
import json
import logging
import os
import requests
from rest_framework.decorators import api_view, schema

# from silk.profiling.profiler import silk_profile

from google_measurement_protocol import event, report
import jwt
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error
from requests_oauthlib import OAuth2Session
import sentry_sdk

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, connections, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.fxa.views import FirefoxAccountsOAuth2Adapter

from emails.models import (
    CannotMakeSubdomainException,
    DomainAddress,
    RelayAddress,
    valid_available_subdomain,
)
from emails.utils import incr_if_enabled
from privaterelay.utils import get_premium_countries_info_from_request


FXA_PROFILE_CHANGE_EVENT = "https://schemas.accounts.firefox.com/event/profile-change"
FXA_SUBSCRIPTION_CHANGE_EVENT = (
    "https://schemas.accounts.firefox.com/event/subscription-state-change"
)
FXA_DELETE_EVENT = "https://schemas.accounts.firefox.com/event/delete-user"
PROFILE_EVENTS = [FXA_PROFILE_CHANGE_EVENT, FXA_SUBSCRIPTION_CHANGE_EVENT]

logger = logging.getLogger("events")
info_logger = logging.getLogger("eventsinfo")


@lru_cache(maxsize=None)
def _get_fxa(request):
    return request.user.socialaccount_set.filter(provider="fxa").first()


@api_view()
@schema(None)
@require_http_methods(["GET"])
def profile_refresh(request):
    if not request.user or request.user.is_anonymous:
        return redirect(reverse("fxa_login"))
    profile = request.user.profile_set.get()

    fxa = _get_fxa(request)
    update_fxa(fxa)
    if "clicked-purchase" in request.COOKIES and profile.has_premium:
        event = "user_purchased_premium"
        incr_if_enabled(event, 1)

    return JsonResponse({})


@api_view(["POST", "GET"])
@schema(None)
@require_http_methods(["POST", "GET"])
def profile_subdomain(request):
    if not request.user or request.user.is_anonymous:
        return redirect(reverse("fxa_login"))
    profile = request.user.profile_set.get()
    if not profile.has_premium:
        raise CannotMakeSubdomainException("error-premium-check-subdomain")
    try:
        if request.method == "GET":
            subdomain = request.GET.get("subdomain", None)
            available = valid_available_subdomain(subdomain)
            return JsonResponse({"available": available})
        else:
            subdomain = request.POST.get("subdomain", None)
            profile.add_subdomain(subdomain)
            return JsonResponse(
                {"status": "Accepted", "message": "success-subdomain-registered"},
                status=202,
            )
    except CannotMakeSubdomainException as e:
        return JsonResponse({"message": e.message, "subdomain": subdomain}, status=400)


def version(request):
    # If version.json is available (from Circle job), serve that
    VERSION_JSON_PATH = os.path.join(settings.BASE_DIR, "version.json")
    if os.path.isfile(VERSION_JSON_PATH):
        with open(VERSION_JSON_PATH) as version_file:
            return JsonResponse(json.load(version_file))

    # Generate version.json contents
    git_dir = os.path.join(settings.BASE_DIR, ".git")
    with open(os.path.join(git_dir, "HEAD")) as head_file:
        ref = head_file.readline().split(" ")[-1].strip()

    with open(os.path.join(git_dir, ref)) as git_hash_file:
        git_hash = git_hash_file.readline().strip()

    version_data = {
        "source": "https://github.com/groovecoder/private-relay",
        "version": git_hash,
        "commit": git_hash,
        "build": "uri to CI build job",
    }
    return JsonResponse(version_data)


def heartbeat(request):
    db_conn = connections["default"]
    c = db_conn.cursor()
    return HttpResponse("200 OK", status=200)


def lbheartbeat(request):
    return HttpResponse("200 OK", status=200)


@csrf_exempt
@require_http_methods(["POST"])
def metrics_event(request):
    try:
        request_data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"msg": "Could not decode JSON"}, status=415)
    if "ga_uuid" not in request_data:
        return JsonResponse({"msg": "No GA uuid found"}, status=404)
    # "dimension5" is a Google Analytics-specific variable to track a custom dimension.
    # This dimension is used to determine which browser vendor the add-on is using: Firefox or Chrome
    event_data = event(
        request_data.get("category", None),
        request_data.get("action", None),
        request_data.get("label", None),
        request_data.get("value", None),
        dimension5=request_data.get("dimension5", None),
    )
    try:
        report(settings.GOOGLE_ANALYTICS_ID, request_data.get("ga_uuid"), event_data)
    except Exception as e:
        logger.error("metrics_event", extra={"error": e})
        return JsonResponse({"msg": "Unable to report metrics event."}, status=500)
    return JsonResponse({"msg": "OK"}, status=200)


@csrf_exempt
def fxa_rp_events(request):
    req_jwt = _parse_jwt_from_request(request)
    authentic_jwt = _authenticate_fxa_jwt(req_jwt)
    event_keys = _get_event_keys_from_jwt(authentic_jwt)
    try:
        social_account = _get_account_from_jwt(authentic_jwt)
    except SocialAccount.DoesNotExist as e:
        # capture an exception in sentry, but don't error, or FXA will retry
        sentry_sdk.capture_exception(e)
        return HttpResponse("202 Accepted", status=202)

    for event_key in event_keys:
        if event_key in PROFILE_EVENTS:
            if settings.DEBUG:
                info_logger.info(
                    "fxa_profile_update",
                    extra={
                        "jwt": authentic_jwt,
                        "event_key": event_key,
                    },
                )
            update_fxa(social_account, authentic_jwt, event_key)
        if event_key == FXA_DELETE_EVENT:
            _handle_fxa_delete(authentic_jwt, social_account, event_key)
    return HttpResponse("200 OK", status=200)


def _parse_jwt_from_request(request):
    request_auth = request.headers["Authorization"]
    return request_auth.split("Bearer ")[1]


def _authenticate_fxa_jwt(req_jwt):
    private_relay_config = apps.get_app_config("privaterelay")
    authentic_jwt = _verify_jwt_with_fxa_key(req_jwt, private_relay_config)

    if not authentic_jwt:
        # FXA key may be old? re-fetch FXA keys and try again
        private_relay_config.ready()
        authentic_jwt = _verify_jwt_with_fxa_key(req_jwt, private_relay_config)
        if not authentic_jwt:
            raise Exception("Could not authenticate JWT with FXA key.")

    return authentic_jwt


def _verify_jwt_with_fxa_key(req_jwt, private_relay_config):
    if not private_relay_config.fxa_verifying_keys:
        raise Exception("FXA verifying keys are not available.")
    social_app = SocialApp.objects.get(provider="fxa")
    for verifying_key in private_relay_config.fxa_verifying_keys:
        if verifying_key["alg"] == "RS256":
            verifying_key = jwt.algorithms.RSAAlgorithm.from_jwk(
                json.dumps(verifying_key)
            )
            return jwt.decode(
                req_jwt,
                verifying_key,
                audience=social_app.client_id,
                algorithms=["RS256"],
            )


def _get_account_from_jwt(authentic_jwt):
    social_account_uid = authentic_jwt["sub"]
    return SocialAccount.objects.get(uid=social_account_uid)


def _get_event_keys_from_jwt(authentic_jwt):
    return authentic_jwt["events"].keys()


def update_fxa(social_account, authentic_jwt=None, event_key=None):
    try:
        client = _get_oauth2_session(social_account)
    except NoSocialToken as e:
        sentry_sdk.capture_exception(e)
        return HttpResponse("202 Accepted", status=202)

    # TODO: more graceful handling of profile fetch failures
    try:
        resp = client.get(FirefoxAccountsOAuth2Adapter.profile_url)
    except CustomOAuth2Error as e:
        sentry_sdk.capture_exception(e)
        return HttpResponse("202 Accepted", status=202)

    extra_data = resp.json()

    try:
        new_email = extra_data["email"]
    except KeyError as e:
        sentry_sdk.capture_exception(e)
        return HttpResponse("202 Accepted", status=202)

    if authentic_jwt and event_key:
        info_logger.info(
            "fxa_rp_event",
            extra={
                "fxa_uid": authentic_jwt["sub"],
                "event_key": event_key,
                "real_address": sha256(new_email.encode("utf-8")).hexdigest(),
            },
        )

    return _update_all_data(social_account, extra_data, new_email)


def _update_all_data(social_account, extra_data, new_email):
    try:
        profile = social_account.user.profile_set.get()
        had_premium = profile.has_premium
        had_phone = profile.has_phone
        with transaction.atomic():
            social_account.extra_data = extra_data
            social_account.save()
            profile = social_account.user.profile_set.get()
            now_has_premium = profile.has_premium
            newly_premium = not had_premium and now_has_premium
            no_longer_premium = had_premium and not now_has_premium
            if newly_premium:
                incr_if_enabled("user_purchased_premium", 1)
                profile.date_subscribed = datetime.now(timezone.utc)
                profile.save()
            if no_longer_premium:
                incr_if_enabled("user_has_downgraded", 1)
            now_has_phone = profile.has_phone
            newly_phone = not had_phone and now_has_phone
            no_longer_phone = had_phone and not now_has_phone
            if newly_phone:
                incr_if_enabled("user_purchased_phone", 1)
                profile.date_subscribed_phone = datetime.now(timezone.utc)
                profile.save()
            if no_longer_phone:
                incr_if_enabled("user_has_dropped_phone", 1)
            social_account.user.email = new_email
            social_account.user.save()
            email_address_record = social_account.user.emailaddress_set.first()
            email_address_record.email = new_email
            email_address_record.save()
            return HttpResponse("202 Accepted", status=202)
    except IntegrityError as e:
        sentry_sdk.capture_exception(e)
        return HttpResponse("Conflict", status=409)


def _handle_fxa_delete(authentic_jwt, social_account, event_key):
    # TODO: Loop over the user's relay addresses and manually call delete()
    # to create hard bounce receipt rules in SES,
    # because cascade deletes like this don't necessarily call delete()
    social_account.user.delete()
    info_logger.info(
        "fxa_rp_event",
        extra={
            "fxa_uid": authentic_jwt["sub"],
            "event_key": event_key,
        },
    )


class NoSocialToken(Exception):
    """The SocialAccount has no SocialToken"""

    def __init__(self, uid, *args, **kwargs):
        self.uid = uid
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f'NoSocialToken: The SocialAccount "{self.uid}" has no token.'

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.uid}")'


# use "raw" requests_oauthlib to automatically refresh the access token
# https://github.com/pennersr/django-allauth/issues/420#issuecomment-301805706
def _get_oauth2_session(social_account):
    refresh_token_url = FirefoxAccountsOAuth2Adapter.access_token_url
    social_token = social_account.socialtoken_set.first()
    if social_token is None:
        raise NoSocialToken(uid=social_account.uid)

    def _token_updater(new_token):
        update_social_token(social_token, new_token)

    client_id = social_token.app.client_id
    client_secret = social_token.app.secret

    extra = {
        "client_id": client_id,
        "client_secret": client_secret,
    }

    expires_in = (social_token.expires_at - datetime.now(timezone.utc)).total_seconds()
    token = {
        "access_token": social_token.token,
        "refresh_token": social_token.token_secret,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }

    client = OAuth2Session(
        client_id,
        token=token,
        auto_refresh_url=refresh_token_url,
        auto_refresh_kwargs=extra,
        token_updater=_token_updater,
    )
    return client


def update_social_token(existing_social_token, new_oauth2_token):
    existing_social_token.token = new_oauth2_token["access_token"]
    existing_social_token.token_secret = new_oauth2_token["refresh_token"]
    existing_social_token.expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(new_oauth2_token["expires_in"])
    )
    existing_social_token.save()
