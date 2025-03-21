import { NextPage } from "next";
import { Localized, useLocalization } from "@fluent/react";
import styles from "./waitlist.module.scss";
import { Layout } from "../../components/layout/Layout";
import { Button } from "../../components/Button";
import { FormEventHandler, useEffect, useState } from "react";
import { getLocale } from "../../functions/getLocale";
import { toast } from "react-toastify";
import { CountryPicker } from "../../components/waitlist/CountryPicker";
import { useRuntimeData } from "../../hooks/api/runtimeData";
import { LocalePicker } from "../../components/waitlist/LocalePicker";
import { useUsers } from "../../hooks/api/user";

/** These are the languages that marketing can send emails in: */
const supportedLocales = ["en", "es", "pl", "pt", "ja"];

const PremiumWaitlist: NextPage = () => {
  const { l10n } = useLocalization();
  const currentLocale = getLocale(l10n);
  const runtimeData = useRuntimeData();
  const currentCountry =
    runtimeData.data?.PERIODICAL_PREMIUM_PLANS.country_code.toUpperCase() ??
    (currentLocale.split("-")[1]?.toUpperCase() as string | undefined);
  const [country, setCountry] = useState<string>();
  const [locale, setLocale] = useState<string>(
    supportedLocales.find(
      (supportedLocale) =>
        supportedLocale.toLowerCase() ===
        currentLocale.split("-")[0].toLowerCase()
    ) ?? "en"
  );
  const usersData = useUsers();
  const [email, setEmail] = useState<string | undefined>(
    usersData.data?.[0]?.email
  );

  useEffect(() => {
    if (
      typeof email === "undefined" &&
      typeof usersData.data?.[0]?.email === "string"
    ) {
      setEmail(usersData.data[0].email);
    }
  }, [email, usersData]);

  const onSubmit: FormEventHandler = async (event) => {
    event.preventDefault();

    if (!email) {
      // Modern browsers should prevent this from happening, due to the `required` attribute:
      console.error(
        "PremiumWaitlist.onSubmit: form submitted while required input field was empty."
      );
      return;
    }

    try {
      const response = await subscribe({
        // The back-end should provide the URL to Basket, pointing to its dev environment
        // if running on stage. If the back-end's response doesn't come in in time,
        // we just assume production:
        basketOrigin:
          runtimeData.data?.BASKET_ORIGIN ?? "https://basket.mozilla.org",
        email: email,
        countryCode: country ?? currentCountry ?? "US",
        locale: locale,
        detectedCountry: currentCountry,
      });
      const body: BasketResponseBody = await response.json();
      if (response.ok && body.status === "ok") {
        toast(l10n.getString("waitlist-subscribe-success"), {
          type: "success",
        });
      } else {
        toast(l10n.getString("waitlist-subscribe-error-unknown"), {
          type: "error",
        });
      }
    } catch (error) {
      toast(l10n.getString("waitlist-subscribe-error-connection"), {
        type: "error",
      });
    }
  };

  return (
    <Layout theme="premium" runtimeData={runtimeData.data}>
      <main className={styles.wrapper}>
        <form onSubmit={onSubmit} className={styles.form}>
          <h2 className={styles.heading}>
            {l10n.getString("waitlist-heading")}
          </h2>
          <p className={styles.lead}>{l10n.getString("waitlist-lead")}</p>
          <div className={styles.controls}>
            <div className={styles.control}>
              <label htmlFor="email">
                {l10n.getString("waitlist-control-email-label")}
              </label>
              <i>{l10n.getString("waitlist-control-required")}</i>
              <input
                type="email"
                name="email"
                id="email"
                value={email ?? ""}
                required={true}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={l10n.getString(
                  "waitlist-control-email-placeholder"
                )}
              />
            </div>
            <div className={styles.control}>
              <label htmlFor="country">
                {l10n.getString("waitlist-control-country-label-2")}
              </label>
              <i>{l10n.getString("waitlist-control-required")}</i>
              <CountryPicker
                name="country"
                id="country"
                value={country ?? currentCountry ?? "US"}
                onChange={(event) =>
                  setCountry(
                    event.target.selectedOptions.item(0)?.value ?? country
                  )
                }
                required={true}
              />
            </div>
            <div className={styles.control}>
              <label htmlFor="locale">
                {l10n.getString("waitlist-control-locale-label")}
              </label>
              <i>{l10n.getString("waitlist-control-required")}</i>
              <LocalePicker
                name="locale"
                id="locale"
                value={locale}
                onChange={(event) =>
                  setLocale(
                    event.target.selectedOptions.item(0)?.value ?? locale
                  )
                }
                supportedLocales={supportedLocales}
                required={true}
              />
            </div>
          </div>
          <Button type="submit">
            {l10n.getString("waitlist-submit-label")}
          </Button>
          <div className={styles.privacy}>
            <Localized
              id="waitlist-privacy-policy-agree"
              elems={{
                a: (
                  <a
                    href="https://www.mozilla.org/privacy/firefox-relay/"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                ),
              }}
            >
              <p />
            </Localized>
            <p>{l10n.getString("waitlist-privacy-policy-use")}</p>
          </div>
        </form>
      </main>
    </Layout>
  );
};

type SubscribeParameters = {
  basketOrigin: string;
  email: string;
  countryCode: string;
  locale: string;
  detectedCountry?: string;
};

/**
 * @see {@link https://basket.readthedocs.io/newsletter_api.html}
 */
type BasketRequestBody = {
  email: string;
  /** comma-delimited list of newsletters */
  newsletters: string;
  format?: "H" | "html" | "T" | "text";
  country?: string;
  /**
   * `relay_country` is a special parameter added just for Relay.
   * It contains the country code selected by the user,
   * as opposed to `country`, which contains the country we detected the user
   * to be in.
   */
  relay_country?: string;
  lang?: string;
  first_name?: string;
  last_name?: string;
  optin?: "N";
  trigger_welcome?: "Y" | "N";
  sync?: "N";
  source_url?: string;
};
type BasketResponseBody =
  | { status: "ok" }
  | { status: "error"; code: number; desc: string };
/**
 * Subscribe someone to a newsletter using the newsletter API.
 *
 * @see {@link https://basket.readthedocs.io/newsletter_api.html}
 */
async function subscribe(params: SubscribeParameters): Promise<Response> {
  const url = `${params.basketOrigin}/news/subscribe/`;
  const body: BasketRequestBody = {
    email: params.email,
    newsletters: "relay-waitlist",
    format: "html",
    country: params.detectedCountry,
    relay_country: params.countryCode,
    lang: params.locale,
    source_url: document.location.origin + document.location.pathname,
  };

  const response = await fetch(url, {
    method: "POST",
    body: new URLSearchParams(body).toString(),
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });

  return response;
}

export default PremiumWaitlist;
