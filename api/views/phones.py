from datetime import datetime, timezone
import logging

import phonenumbers

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.forms import model_to_dict

from rest_framework import (
    decorators,
    permissions,
    response,
    throttling,
    viewsets,
    exceptions,
)
from rest_framework.generics import get_object_or_404

from twilio.base.exceptions import TwilioRestException

from api.views import SaveToRequestUser
from emails.models import Profile, get_storing_phone_log
from emails.utils import incr_if_enabled

from phones.models import (
    InboundContact,
    RealPhone,
    RelayNumber,
    get_last_text_sender,
    get_pending_unverified_realphone_records,
    get_valid_realphone_verification_record,
    get_verified_realphone_record,
    get_verified_realphone_records,
    send_welcome_message,
    suggested_numbers,
    location_numbers,
    area_code_numbers,
    twilio_client,
)

from ..exceptions import ConflictError
from ..permissions import HasPhoneService
from ..renderers import (
    TemplateTwiMLRenderer,
    vCardRenderer,
)
from ..serializers.phones import (
    InboundContactSerializer,
    RealPhoneSerializer,
    RelayNumberSerializer,
)


logger = logging.getLogger("events")
info_logger = logging.getLogger("eventsinfo")


def twilio_validator():
    phones_config = apps.get_app_config("phones")
    validator = phones_config.twilio_validator
    return validator


def twiml_app():
    phones_config = apps.get_app_config("phones")
    return phones_config.twiml_app


class RealPhoneRateThrottle(throttling.UserRateThrottle):
    rate = settings.PHONE_RATE_LIMIT


class RealPhoneViewSet(SaveToRequestUser, viewsets.ModelViewSet):
    """
    Get real phone number records for the authenticated user.

    The authenticated user must have a subscription that grants one of the
    `SUBSCRIPTIONS_WITH_PHONE` capabilities.

    Client must be authenticated, and these endpoints only return data that is
    "owned" by the authenticated user.

    All endpoints are rate-limited to settings.PHONE_RATE_LIMIT
    """

    http_method_names = ["get", "post", "patch", "delete"]
    permission_classes = [permissions.IsAuthenticated, HasPhoneService]
    serializer_class = RealPhoneSerializer
    # TODO: this doesn't seem to e working?
    throttle_classes = [RealPhoneRateThrottle]

    def get_queryset(self):
        return RealPhone.objects.filter(user=self.request.user)

    def create(self, request):
        """
        Add real phone number to the authenticated user.

        The "flow" to verify a real phone number is:
        1. POST a number (Will text a verification code to the number)
        2a. PATCH the verification code to the realphone/{id} endpoint
        2b. POST the number and verification code together

        The authenticated user must have a subscription that grants one of the
        `SUBSCRIPTIONS_WITH_PHONE` capabilities.

        The `number` field should be in [E.164][e164] format which includes a country
        code. If the number is not in E.164 format, this endpoint will try to
        create an E.164 number by prepending the country code of the client
        making the request (i.e., from the `X-Client-Region` HTTP header).

        If the `POST` does NOT include a `verification_code` and the number is
        a valid (currently, US-based) number, this endpoint will text a
        verification code to the number.

        If the `POST` DOES include a `verification_code`, and the code matches
        a code already sent to the number, this endpoint will set `verified` to
        `True` for this number.

        [e164]: https://en.wikipedia.org/wiki/E.164
        """
        incr_if_enabled("phones_RealPhoneViewSet.create")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if the request includes a valid verification_code
        # value, look for any un-expired record that matches both the phone
        # number and verification code and mark it verified.
        verification_code = serializer.validated_data.get("verification_code")
        if verification_code:
            valid_record = get_valid_realphone_verification_record(
                request.user, serializer.validated_data["number"], verification_code
            )
            if not valid_record:
                incr_if_enabled("phones_RealPhoneViewSet.create.invalid_verification")
                raise exceptions.ValidationError(
                    "Could not find that verification_code for user and number. It may have expired."
                )

            headers = self.get_success_headers(serializer.validated_data)
            verified_valid_record = valid_record.mark_verified()
            incr_if_enabled("phones_RealPhoneViewSet.create.mark_verified")
            response_data = model_to_dict(
                verified_valid_record,
                fields=[
                    "id",
                    "number",
                    "verification_sent_date",
                    "verified",
                    "verified_date",
                ],
            )
            return response.Response(response_data, status=201, headers=headers)

        # to prevent sending verification codes to verified numbers,
        # check if the number is already a verified number.
        is_verified = get_verified_realphone_record(serializer.validated_data["number"])
        if is_verified:
            raise ConflictError("A verified record already exists for this number.")

        # to prevent abusive sending of verification messages,
        # check if there is an un-expired verification code for the user
        pending_unverified_records = get_pending_unverified_realphone_records(
            serializer.validated_data["number"]
        )
        if pending_unverified_records:
            raise ConflictError(
                "An unverified record already exists for this number.",
            )

        # We call an additional _validate_number function with the request
        # to try to parse the number as a local national number in the
        # request.country attribute
        valid_number = _validate_number(request)
        serializer.validated_data["number"] = valid_number.phone_number
        serializer.validated_data["country_code"] = valid_number.country_code.upper()

        self.perform_create(serializer)
        incr_if_enabled("phones_RealPhoneViewSet.perform_create")
        headers = self.get_success_headers(serializer.validated_data)
        response_data = serializer.data
        response_data["message"] = (
            "Sent verification code to "
            f"{valid_number.phone_number} "
            f"(country: {valid_number.country_code} "
            f"carrier: {valid_number.carrier})"
        )
        return response.Response(response_data, status=201, headers=headers)

    # check verification_code during partial_update to compare
    # the value sent in the request against the value already on the instance
    # TODO: this logic might be able to move "up" into the model, but it will
    # need some more serious refactoring of the RealPhone.save() method
    def partial_update(self, request, *args, **kwargs):
        """
        Update the authenticated user's real phone number.

        The authenticated user must have a subscription that grants one of the
        `SUBSCRIPTIONS_WITH_PHONE` capabilities.

        The `{id}` should match a previously-`POST`ed resource that belongs to the user.

        The `number` field should be in [E.164][e164] format which includes a country
        code.

        The `verification_code` should be the code that was texted to the
        number during the `POST`. If it matches, this endpoint will set
        `verified` to `True` for this number.

        [e164]: https://en.wikipedia.org/wiki/E.164
        """
        incr_if_enabled("phones_RealPhoneViewSet.partial_update")
        instance = self.get_object()
        if request.data["number"] != instance.number:
            raise exceptions.ValidationError("Invalid number for ID.")
        # TODO: check verification_sent_date is not "expired"?
        # Note: the RealPhone.save() logic should prevent expired verifications
        if (
            "verification_code" not in request.data
            or not request.data["verification_code"] == instance.verification_code
        ):
            raise exceptions.ValidationError(
                "Invalid verification_code for ID. It may have expired."
            )

        instance.mark_verified()
        incr_if_enabled("phones_RealPhoneViewSet.partial_update.mark_verified")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a real phone resource.

        Only **un-verified** real phone resources can be deleted.
        """
        incr_if_enabled("phones_RealPhoneViewSet.destroy")
        instance = self.get_object()
        if instance.verified:
            raise exceptions.ValidationError(
                "Only un-verified real phone resources can be deleted."
            )

        return super().destroy(request, *args, **kwargs)


class RelayNumberViewSet(SaveToRequestUser, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch"]
    permission_classes = [permissions.IsAuthenticated, HasPhoneService]
    serializer_class = RelayNumberSerializer

    def get_queryset(self):
        return RelayNumber.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Provision a phone number with Twilio and assign to the authenticated user.

        ⚠️ **THIS WILL BUY A PHONE NUMBER** ⚠️
        If you have real account credentials in your `TWILIO_*` env vars, this
        will really provision a Twilio number to your account. You can use
        [Test Credentials][test-creds] to call this endpoint without making a
        real phone number purchase. If you do, you need to pass one of the
        [test phone numbers][test-numbers].

        The `number` should be in [E.164][e164] format.

        Every call or text to the relay number will be sent as a webhook to the
        URL configured for your `TWILIO_SMS_APPLICATION_SID`.

        [test-creds]: https://www.twilio.com/docs/iam/test-credentials
        [test-numbers]: https://www.twilio.com/docs/iam/test-credentials#test-incoming-phone-numbers-parameters-PhoneNumber
        [e164]: https://en.wikipedia.org/wiki/E.164
        """
        incr_if_enabled("phones_RelayNumberViewSet.create")
        existing_number = RelayNumber.objects.filter(user=request.user)
        if existing_number:
            raise exceptions.ValidationError("User already has a RelayNumber.")
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        Update the authenticated user's relay number.

        The authenticated user must have a subscription that grants one of the
        `SUBSCRIPTIONS_WITH_PHONE` capabilities.

        The `{id}` should match a previously-`POST`ed resource that belongs to the authenticated user.

        This is primarily used to toggle the `enabled` field.
        """
        incr_if_enabled("phones_RelayNumberViewSet.partial_update")
        return super().partial_update(request, *args, **kwargs)

    @decorators.action(detail=False)
    def suggestions(self, request):
        """
        Returns suggested relay numbers for the authenticated user.

        Based on the user's real number, returns available relay numbers:
          * `same_prefix_options`: Numbers that match as much of the user's real number as possible.
          * `other_areas_options`: Numbers that exactly match the user's real number, in a different area code.
          * `same_area_options`: Other numbers in the same area code as the user.
          * `random_options`: Available numbers in the user's country
        """
        incr_if_enabled("phones_RelayNumberViewSet.suggestions")
        numbers = suggested_numbers(request.user)
        return response.Response(numbers)

    @decorators.action(detail=False)
    def search(self, request):
        """
        Search for available numbers.

        This endpoints uses the underlying [AvailablePhoneNumbers][apn] API.

        Accepted query params:
          * ?location=
            * Will be passed to `AvailablePhoneNumbers` `in_locality` param
          * ?area_code=
            * Will be passed to `AvailablePhoneNumbers` `area_code` param

        [apn]: https://www.twilio.com/docs/phone-numbers/api/availablephonenumberlocal-resource#read-multiple-availablephonenumberlocal-resources
        """
        incr_if_enabled("phones_RelayNumberViewSet.search")
        real_phone = get_verified_realphone_records(request.user).first()
        if real_phone:
            country_code = real_phone.country_code
        else:
            country_code = "US"
        location = request.query_params.get("location")
        if location is not None:
            numbers = location_numbers(location, country_code)
            return response.Response(numbers)

        area_code = request.query_params.get("area_code")
        if area_code is not None:
            numbers = area_code_numbers(area_code, country_code)
            return response.Response(numbers)

        return response.Response({}, 404)


class InboundContactViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "patch"]
    permission_classes = [permissions.IsAuthenticated, HasPhoneService]
    serializer_class = InboundContactSerializer

    def get_queryset(self):
        request_user_relay_num = get_object_or_404(RelayNumber, user=self.request.user)
        return InboundContact.objects.filter(relay_number=request_user_relay_num)


def _validate_number(request):
    parsed_number = _parse_number(
        request.data["number"], getattr(request, "country", None)
    )
    if not parsed_number:
        country = None
        if hasattr(request, "country"):
            country = request.country
        error_message = f"number must be in E.164 format, or in local national format of the country detected: {country}"
        raise exceptions.ValidationError(error_message)

    e164_number = f"+{parsed_number.country_code}{parsed_number.national_number}"
    number_details = _get_number_details(e164_number)
    if not number_details:
        raise exceptions.ValidationError(
            f"Could not get number details for {e164_number}"
        )

    if number_details.country_code.upper() not in settings.TWILIO_ALLOWED_COUNTRY_CODES:
        incr_if_enabled("phones_validate_number_unsupported_country")
        raise exceptions.ValidationError(
            "Relay Phone is currently only available for these country codes: "
            f"{sorted(settings.TWILIO_ALLOWED_COUNTRY_CODES)!r}. "
            "Your phone number country code is: "
            f"'{number_details.country_code.upper()}'."
        )

    return number_details


def _parse_number(number, country=None):
    try:
        # First try to parse assuming number is E.164 with country prefix
        return phonenumbers.parse(number)
    except phonenumbers.phonenumberutil.NumberParseException as e:
        if e.error_type == e.INVALID_COUNTRY_CODE and country is not None:
            try:
                # Try to parse, assuming number is local national format
                # in the detected request country
                return phonenumbers.parse(number, country)
            except Exception:
                return None
    return None


def _get_number_details(e164_number):
    incr_if_enabled("phones_get_number_details")
    try:
        client = twilio_client()
        return client.lookups.v1.phone_numbers(e164_number).fetch(type=["carrier"])
    except Exception:
        logger.exception(f"Could not get number details for {e164_number}")
        return None


@decorators.api_view()
@decorators.permission_classes([permissions.AllowAny])
@decorators.renderer_classes([vCardRenderer])
def vCard(request, lookup_key):
    """
    Get a Relay vCard. `lookup_key` should be passed in url path.

    We use this to return a vCard for a number. When we create a RelayNumber,
    we create a secret lookup_key and text it to the user.
    """
    incr_if_enabled("phones_vcard")
    if lookup_key is None:
        return response.Response(status=404)

    try:
        relay_number = RelayNumber.objects.get(vcard_lookup_key=lookup_key)
    except RelayNumber.DoesNotExist:
        raise exceptions.NotFound()
    number = relay_number.number

    resp = response.Response({"number": number})
    resp["Content-Disposition"] = f"attachment; filename={number}.vcf"
    return resp


@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.IsAuthenticated, HasPhoneService])
def resend_welcome_sms(request):
    """
    Resend the "Welcome" SMS, including vCard.

    Requires the user to be signed in and to have phone service.
    """
    incr_if_enabled("phones_resend_welcome_sms")
    try:
        relay_number = RelayNumber.objects.get(user=request.user)
    except RelayNumber.DoesNotExist:
        raise exceptions.NotFound()
    send_welcome_message(request.user, relay_number)

    resp = response.Response(status=201, data={"msg": "sent"})
    return resp


def _try_delete_from_twilio(message):
    try:
        message.delete()
    except TwilioRestException as e:
        # Raise the exception unless it's a 404 indicating the message is already gone
        if e.status != 404:
            raise e


@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.AllowAny])
@decorators.renderer_classes([TemplateTwiMLRenderer])
def inbound_sms(request):
    incr_if_enabled("phones_inbound_sms")
    _validate_twilio_request(request)

    """
    TODO: delete the message from Twilio; how to do this AFTER this request? queue?
    E.g., with a django-celery task in phones.tasks:

    inbound_msg_sid = request.data.get("MessageSid", None)
    if inbound_msg_sid is None:
        raise exceptions.ValidationError("Request missing MessageSid")
    tasks._try_delete_from_twilio.delay(args=message, countdown=10)
    """

    inbound_body = request.data.get("Body", None)
    inbound_from = request.data.get("From", None)
    inbound_to = request.data.get("To", None)
    if inbound_body is None or inbound_from is None or inbound_to is None:
        raise exceptions.ValidationError("Request missing From, To, Or Body.")

    relay_number, real_phone = _get_phone_objects(inbound_to)
    _check_remaining(relay_number, "texts")

    if inbound_from == real_phone.number:
        _handle_sms_reply(relay_number, real_phone, inbound_body)
        return response.Response(
            status=200,
            template_name="twiml_empty_response.xml",
        )

    number_disabled = _check_disabled(relay_number, "texts")
    if number_disabled:
        return response.Response(
            status=200,
            template_name="twiml_empty_response.xml",
        )
    inbound_contact = _get_inbound_contact(relay_number, inbound_from)
    if inbound_contact:
        _check_and_update_contact(inbound_contact, "texts", relay_number)

    client = twilio_client()
    app = twiml_app()
    incr_if_enabled("phones_outbound_sms")
    client.messages.create(
        from_=relay_number.number,
        body=f"[Relay 📲 {inbound_from}] {inbound_body}",
        status_callback=app.sms_status_callback,
        to=real_phone.number,
    )
    relay_number.remaining_texts -= 1
    relay_number.texts_forwarded += 1
    relay_number.save()
    return response.Response(
        status=201,
        template_name="twiml_empty_response.xml",
    )


@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.AllowAny])
@decorators.renderer_classes([TemplateTwiMLRenderer])
def inbound_call(request):
    incr_if_enabled("phones_inbound_call")
    _validate_twilio_request(request)
    inbound_from = request.data.get("Caller", None)
    inbound_to = request.data.get("Called", None)
    if inbound_from is None or inbound_to is None:
        raise exceptions.ValidationError("Call data missing Caller or Called.")

    relay_number, real_phone = _get_phone_objects(inbound_to)

    number_disabled = _check_disabled(relay_number, "calls")
    if number_disabled:
        say = "Sorry, that number is not available."
        return response.Response(
            {"say": say}, status=200, template_name="twiml_blocked.xml"
        )

    _check_remaining(relay_number, "seconds")

    inbound_contact = _get_inbound_contact(relay_number, inbound_from)
    if inbound_contact:
        _check_and_update_contact(inbound_contact, "calls", relay_number)

    relay_number.calls_forwarded += 1
    relay_number.save()

    # Note: TemplateTwiMLRenderer will render this as TwiML
    incr_if_enabled("phones_outbound_call")
    return response.Response(
        {"inbound_from": inbound_from, "real_number": real_phone.number},
        status=201,
        template_name="twiml_dial.xml",
    )


@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.AllowAny])
def voice_status(request):
    incr_if_enabled("phones_voice_status")
    _validate_twilio_request(request)
    call_sid = request.data.get("CallSid", None)
    called = request.data.get("Called", None)
    call_status = request.data.get("CallStatus", None)
    if call_sid is None or called is None or call_status is None:
        raise exceptions.ValidationError("Call data missing Called, CallStatus")
    if call_status != "completed":
        return response.Response(status=200)
    call_duration = request.data.get("CallDuration", None)
    if call_duration is None:
        raise exceptions.ValidationError("completed call data missing CallDuration")
    relay_number, _ = _get_phone_objects(called)
    relay_number.remaining_seconds = relay_number.remaining_seconds - int(call_duration)
    relay_number.save()
    if relay_number.remaining_seconds < 0:
        info_logger.info(
            "phone_limit_exceeded",
            extra={
                "fxa_uid": relay_number.user.profile_set.get().fxa.uid,
                "call_duration_in_seconds": int(call_duration),
                "relay_number_enabled": relay_number.enabled,
                "remaining_seconds": relay_number.remaining_seconds,
                "remaining_minutes": relay_number.remaining_minutes,
            },
        )
    client = twilio_client()
    client.calls(call_sid).delete()
    return response.Response(status=200)


@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.AllowAny])
def sms_status(request):
    _validate_twilio_request(request)
    sms_status = request.data.get("SmsStatus", None)
    message_sid = request.data.get("MessageSid", None)
    if sms_status is None or message_sid is None:
        raise exceptions.ValidationError(
            "Text status data missing SmsStatus or MessageSid"
        )
    if sms_status != "delivered":
        return response.Response(status=200)
    client = twilio_client()
    message = client.messages(message_sid)
    _try_delete_from_twilio(message)
    return response.Response(status=200)


def _get_phone_objects(inbound_to):
    # Get RelayNumber and RealPhone
    try:
        relay_number = RelayNumber.objects.get(number=inbound_to)
        real_phone = RealPhone.objects.get(user=relay_number.user, verified=True)
    except ObjectDoesNotExist:
        raise exceptions.ValidationError("Could not find relay number.")

    return relay_number, real_phone


def _handle_sms_reply(relay_number, real_phone, inbound_body):
    incr_if_enabled("phones_handle_sms_reply")
    client = twilio_client()
    storing_phone_log = get_storing_phone_log(relay_number)
    if not storing_phone_log:
        origin = settings.SITE_ORIGIN
        error = f"You can only reply if you allow Firefox Relay to keep a log of your callers and text senders. {origin}/accounts/settings/"
        client.messages.create(
            from_=relay_number.number,
            body=error,
            to=real_phone.number,
        )
        raise exceptions.ValidationError(error)
    last_text_sender = get_last_text_sender(relay_number)
    if last_text_sender == None:
        error = "Could not find a previous text sender."
        client.messages.create(
            from_=relay_number.number,
            body=error,
            to=real_phone.number,
        )
        raise exceptions.ValidationError(error)
    incr_if_enabled("phones_send_sms_reply")
    client.messages.create(
        from_=relay_number.number,
        body=inbound_body,
        to=last_text_sender.inbound_number,
    )
    relay_number.remaining_texts -= 1
    relay_number.texts_forwarded += 1
    relay_number.save()


def _check_disabled(relay_number, contact_type):
    # Check if RelayNumber is disabled
    if not relay_number.enabled:
        attr = f"{contact_type}_blocked"
        incr_if_enabled(f"phones_{contact_type}_global_blocked")
        setattr(relay_number, attr, getattr(relay_number, attr) + 1)
        relay_number.save()
        return True


def _check_remaining(relay_number, resource_type):
    model_attr = f"remaining_{resource_type}"
    if getattr(relay_number, model_attr) <= 0:
        incr_if_enabled(f"phones_out_of_{resource_type}")
        raise exceptions.ValidationError(f"Number is out of {resource_type}.")
    return True


def _get_inbound_contact(relay_number, inbound_from):
    # Check if RelayNumber is storing phone log
    profile = Profile.objects.get(user=relay_number.user)
    if not profile.store_phone_log:
        return None

    # Check if RelayNumber is blocking this inbound_from
    inbound_contact, _ = InboundContact.objects.get_or_create(
        relay_number=relay_number, inbound_number=inbound_from
    )
    return inbound_contact


def _check_and_update_contact(inbound_contact, contact_type, relay_number):
    if inbound_contact.blocked:
        incr_if_enabled(f"phones_{contact_type}_specific_blocked")
        contact_attr = f"num_{contact_type}_blocked"
        setattr(
            inbound_contact, contact_attr, getattr(inbound_contact, contact_attr) + 1
        )
        inbound_contact.save()
        relay_attr = f"{contact_type}_blocked"
        setattr(relay_number, relay_attr, getattr(relay_number, relay_attr) + 1)
        relay_number.save()
        raise exceptions.ValidationError(f"Number is not accepting {contact_type}.")

    inbound_contact.last_inbound_date = datetime.now(timezone.utc)
    # strip trailing "s": InboundContact.last_inbound_type is max_length 4
    inbound_contact.last_inbound_type = contact_type[:-1]
    attr = f"num_{contact_type}"
    setattr(inbound_contact, attr, getattr(inbound_contact, attr) + 1)
    inbound_contact.save()


def _validate_twilio_request(request):
    if "X-Twilio-Signature" not in request._request.headers:
        raise exceptions.ValidationError(
            "Invalid request: missing X-Twilio-Signature header."
        )

    url = request._request.build_absolute_uri()
    sorted_params = {}
    for param_key in sorted(request.data):
        sorted_params[param_key] = request.data.get(param_key)
    request_signature = request._request.headers["X-Twilio-Signature"]
    validator = twilio_validator()
    if not validator.validate(url, sorted_params, request_signature):
        incr_if_enabled("phones_invalid_twilio_signature")
        raise exceptions.ValidationError("Invalid request: invalid signature")
