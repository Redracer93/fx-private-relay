import { NextPage } from "next";
import { Layout } from "../components/layout/Layout";
import { useProfiles } from "../hooks/api/profile";
import { useUsers } from "../hooks/api/user";
import { PhoneOnboarding } from "../components/phones/onboarding/PhoneOnboarding";
import { useRelayNumber } from "../hooks/api/relayNumber";
import { useEffect, useState } from "react";
import { PhoneDashboard } from "../components/phones/dashboard/Dashboard";
import { getRuntimeConfig } from "../config";
import { PurchasePhonesPlan } from "../components/phones/onboarding/PurchasePhonesPlan";
import { Banner } from "../components/Banner";
import styles from "./phone.module.scss";
import { useLocalization } from "@fluent/react";
import { useRealPhonesData } from "../hooks/api/realPhone";
import { DashboardSwitcher } from "../components/layout/navigation/DashboardSwitcher";
import { isFlagActive } from "../functions/waffle";
import { useRuntimeData } from "../hooks/api/runtimeData";
import { useRouter } from "next/router";
import { isPhonesAvailableInCountry } from "../functions/getPlan";
import { toast } from "react-toastify";
import { useLocalDismissal } from "../hooks/localDismissal";

const Phone: NextPage = () => {
  const runtimeData = useRuntimeData();
  const profileData = useProfiles();
  const profile = profileData.data?.[0];
  const { l10n } = useLocalization();
  const router = useRouter();

  const userData = useUsers();
  const user = userData.data?.[0];

  const relayNumberData = useRelayNumber();
  const [isInOnboarding, setIsInOnboarding] = useState<boolean>();
  const realPhoneData = useRealPhonesData();
  // The user hasn't completed the onboarding yet if...
  const isNotSetup =
    // ...they haven't purchased the phone plan yet, or...
    profile?.has_phone === false ||
    // ...the API request for their Relay number has completed but returned no
    // result, or...
    (!relayNumberData.isValidating &&
      typeof relayNumberData.error === "undefined" &&
      typeof relayNumberData.data === "undefined") ||
    // ...there was a list of Relay numbers, but it was empty:
    relayNumberData.data?.length === 0;

  const resendWelcomeSMSDismissal = useLocalDismissal(
    `resend-sms-banner-${profile?.id}`
  );

  const resendWelcomeText = !resendWelcomeSMSDismissal.isDismissed && (
    <div className={styles["banner-wrapper"]}>
      <Banner
        title={l10n.getString("phone-banner-resend-welcome-sms-title")}
        type="info"
        cta={{
          content: l10n.getString("phone-banner-resend-welcome-sms-cta"),
          onClick: () => {
            realPhoneData.resendWelcomeSMS();
            toast(l10n.getString("phone-banner-resend-welcome-sms-toast-msg"), {
              type: "success",
            });
            resendWelcomeSMSDismissal.dismiss();
          },
          gaViewPing: {
            category: "Resend Welcome SMS",
            label: "phone-page-banner-resend-welcome",
          },
        }}
        dismissal={{
          key: `resend-sms-banner-${profile?.id}`,
        }}
      >
        {l10n.getString("phone-banner-resend-welcome-sms-body")}
      </Banner>
    </div>
  );

  useEffect(() => {
    if (!runtimeData.data) {
      return;
    }
    if (
      // Send the user to /premium if the phones flag is disabled...
      !isFlagActive(runtimeData.data, "phones") ||
      // ...or if a phone subscription is not available in the current country,
      // and the user has not set it up before (possibly in another country):
      (!isPhonesAvailableInCountry(runtimeData.data) && isNotSetup)
    ) {
      router.push("/premium");
    }
  }, [runtimeData.data, router, isNotSetup]);

  useEffect(() => {
    if (
      typeof isInOnboarding === "undefined" &&
      Array.isArray(relayNumberData.data) &&
      relayNumberData.data.length === 0
    ) {
      setIsInOnboarding(true);
    }
  }, [isInOnboarding, relayNumberData]);

  if (!userData.isValidating && userData.error) {
    document.location.assign(getRuntimeConfig().fxaLoginUrl);
  }

  if (!profile || !user || !relayNumberData.data || !runtimeData.data) {
    // TODO: Show a loading spinner?
    return null;
  }

  // If the user has their phone subscription all set up, show the dashboard:
  if (profile.has_phone && !isInOnboarding && relayNumberData.data.length > 0) {
    return (
      <Layout>
        <DashboardSwitcher />
        <main className={styles["main-wrapper"]}>
          {resendWelcomeText}
          <PhoneDashboard />
        </main>
      </Layout>
    );
  }

  // If the user doesn't have a phone subscription already set up and can't
  // buy it in the country they're in, don't render anything; the `useEffect`
  // above will redirect the user to /premium
  if (!isPhonesAvailableInCountry(runtimeData.data)) {
    return null;
  }

  // show the phone plan purchase page if the user has not purchased phone product
  if (!profile.has_phone) {
    return (
      <Layout>
        <DashboardSwitcher />
        <PurchasePhonesPlan runtimeData={runtimeData.data} />
      </Layout>
    );
  }

  // Otherwise start the onboarding process
  return (
    <Layout>
      <DashboardSwitcher />
      <PhoneOnboarding
        onComplete={() => setIsInOnboarding(false)}
        profile={profile}
        runtimeData={runtimeData.data}
      />
    </Layout>
  );
};

export default Phone;
