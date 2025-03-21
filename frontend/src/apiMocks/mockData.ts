import { CustomAliasData, RandomAliasData } from "../hooks/api/aliases";
import { RealPhoneData } from "../hooks/api/realPhone";
import { RelayNumberData } from "../hooks/api/relayNumber";
import { InboundContactData } from "../hooks/api/inboundContact";
import { ProfileData } from "../hooks/api/profile";
import { RuntimeData } from "../hooks/api/runtimeData";
import { UserData } from "../hooks/api/user";

export const mockIds = ["empty", "onboarding", "some", "full"] as const;

// This is the same for all mock users, at this time:
export const mockedRuntimeData: RuntimeData = {
  FXA_ORIGIN: "https://fxa-mock.com",
  BASKET_ORIGIN: "https://basket-mock.com",
  GOOGLE_ANALYTICS_ID: "UA-123456789-0",
  PERIODICAL_PREMIUM_PRODUCT_ID: "prod_123456789",
  PHONE_PRODUCT_ID: "prod_123456789",
  BUNDLE_PRODUCT_ID: "prod_123456789",
  PERIODICAL_PREMIUM_PLANS: {
    country_code: "nl",
    plan_country_lang_mapping: {
      nl: {
        nl: {
          monthly: {
            id: "price_1JmROfJNcmPzuWtR6od8OfDW",
            price: 2.5,
            currency: "EUR",
          },
          yearly: {
            id: "price_1JmROfJNcmPzuWtR6od8OfDW",
            price: 1.99,
            currency: "EUR",
          },
        },
      },
    },
    countries: ["nl"],
    available_in_country: true,
  },
  PHONE_PLANS: {
    country_code: "nl",
    plan_country_lang_mapping: {
      nl: {
        nl: {
          monthly: {
            id: "price_1JmROfJNcmPzuWtR6od8OfDW",
            price: 5.99,
            currency: "EUR",
          },
          yearly: {
            id: "price_1JmROfJNcmPzuWtR6od8OfDW",
            price: 4.99,
            currency: "EUR",
          },
        },
      },
    },
    countries: ["nl"],
    available_in_country: true,
  },
  BUNDLE_PLANS: {
    country_code: "nl",
    plan_country_lang_mapping: {
      nl: {
        nl: {
          yearly: {
            id: "price_1JmROfJNcmPzuWtR6od8OfDW",
            price: 8.99,
            currency: "EUR",
          },
        },
      },
    },
    countries: ["nl"],
    available_in_country: true,
  },
  WAFFLE_FLAGS: [
    ["new_from_address", true],
    ["tracker_removal", true],
    ["phones", true],
    ["bundle", true],
  ],
  MAX_MINUTES_TO_VERIFY_REAL_PHONE: 5,
};

export const mockedUsers: Record<typeof mockIds[number], UserData> = {
  empty: { email: "empty@example.com" },
  onboarding: { email: "onboarding@example.com" },
  some: { email: "some@example.com" },
  full: { email: "full@example.com" },
};

export const mockedProfiles: Record<typeof mockIds[number], ProfileData> = {
  empty: {
    api_token: "empty",
    avatar: "https://profile.accounts.firefox.com/v1/avatar/e",
    bounce_status: [false, ""],
    date_subscribed: null,
    remove_level_one_email_trackers: false,
    has_premium: false,
    has_phone: false,
    has_vpn: false,
    id: 0,
    next_email_try: "2020-04-09T00:00:00.000Z",
    onboarding_state: 0,
    server_storage: true,
    store_phone_log: true,
    subdomain: null,
    emails_blocked: 0,
    emails_forwarded: 0,
    emails_replied: 0,
    level_one_trackers_blocked: 0,
  },
  onboarding: {
    api_token: "onboarding",
    avatar: "https://profile.accounts.firefox.com/v1/avatar/o",
    bounce_status: [false, ""],
    date_subscribed: "2020-04-09T00:00:00.000Z",
    remove_level_one_email_trackers: false,
    has_premium: true,
    has_phone: true,
    has_vpn: false,
    id: 1,
    next_email_try: "2020-04-09T00:00:00.000Z",
    onboarding_state: 0,
    server_storage: true,
    subdomain: null,
    emails_blocked: 0,
    emails_forwarded: 0,
    emails_replied: 0,
    level_one_trackers_blocked: 0,
    store_phone_log: true,
  },
  some: {
    api_token: "some",
    avatar: "https://profile.accounts.firefox.com/v1/avatar/s",
    bounce_status: [false, ""],
    date_subscribed: "2020-04-09T00:00:00.000Z",
    remove_level_one_email_trackers: false,
    has_premium: true,
    has_phone: true,
    has_vpn: false,
    id: 2,
    next_email_try: "2020-04-09T00:00:00.000Z",
    onboarding_state: 3,
    server_storage: true,
    subdomain: null,
    emails_blocked: 424284,
    emails_forwarded: 1337,
    emails_replied: 40,
    level_one_trackers_blocked: 72,
    store_phone_log: true,
  },
  full: {
    api_token: "full",
    avatar: "https://profile.accounts.firefox.com/v1/avatar/f",
    bounce_status: [true, "soft"],
    date_subscribed: "2020-04-09T00:00:00.000Z",
    remove_level_one_email_trackers: true,
    has_premium: true,
    has_phone: true,
    has_vpn: true,
    id: 3,
    next_email_try: "2020-04-09T00:00:00.000Z",
    onboarding_state: 3,
    server_storage: true,
    subdomain: "mydomain",
    emails_blocked: 848526,
    emails_forwarded: 1337,
    emails_replied: 9631,
    level_one_trackers_blocked: 1409,
    store_phone_log: true,
  },
};
export const mockedRelayaddresses: Record<
  typeof mockIds[number],
  RandomAliasData[]
> = {
  empty: [],
  onboarding: [],
  some: [
    {
      address: "random_0",
      full_address: "random_0@mozmail.com",
      created_at: "2020-04-09T00:00:00.000Z",
      description: "A label",
      domain: 1,
      enabled: true,
      block_list_emails: true,
      block_level_one_trackers: false,
      generated_for: "",
      id: 0,
      last_modified_at: "2020-04-09T00:00:00.000Z",
      last_used_at: "2020-04-09T00:00:00.000Z",
      num_blocked: 42,
      num_forwarded: 1337,
      num_replied: 20,
      num_spam: 0,
      num_level_one_trackers_blocked: 72,
      mask_type: "random",
      used_on: "",
    },
    {
      address: "random_1",
      full_address: "random_1@mozmail.com",
      created_at: "2020-04-09T00:00:00.000Z",
      description: "",
      domain: 1,
      enabled: false,
      block_list_emails: false,
      block_level_one_trackers: false,
      generated_for: "",
      id: 1,
      last_modified_at: "2020-04-09T00:00:00.000Z",
      last_used_at: "2020-04-09T00:00:00.000Z",
      num_blocked: 424242,
      num_forwarded: 0,
      num_replied: 20,
      num_spam: 0,
      num_level_one_trackers_blocked: 0,
      mask_type: "random",
      used_on: "",
    },
  ],
  full: [
    {
      address: "random_0",
      full_address: "random_0@mozmail.com",
      created_at: "2020-04-09T00:00:00.000Z",
      description: "A label",
      domain: 1,
      enabled: true,
      block_list_emails: false,
      block_level_one_trackers: true,
      generated_for: "",
      id: 0,
      last_modified_at: "2020-04-09T00:00:00.000Z",
      last_used_at: "2020-04-09T00:00:00.000Z",
      num_blocked: 42,
      num_forwarded: 1337,
      num_replied: 201,
      num_spam: 0,
      num_level_one_trackers_blocked: 0,
      mask_type: "random",
      used_on: "",
    },
    {
      address: "random_1",
      full_address: "random_1@mozmail.com",
      created_at: "2020-04-09T00:00:00.000Z",
      description: "",
      domain: 1,
      enabled: false,
      block_list_emails: false,
      block_level_one_trackers: true,
      generated_for: "disneyplus.com",
      id: 1,
      last_modified_at: "2020-04-09T00:00:00.000Z",
      last_used_at: "2020-04-09T00:00:00.000Z",
      num_blocked: 424242,
      num_forwarded: 0,
      num_replied: 310,
      num_spam: 0,
      num_level_one_trackers_blocked: 72,
      mask_type: "random",
      used_on: "disneyplus.com,netflix.com",
    },
  ],
};
export const mockedDomainaddresses: Record<
  typeof mockIds[number],
  CustomAliasData[]
> = {
  empty: [],
  onboarding: [],
  some: [],
  full: [
    {
      address: "custom_0",
      full_address: "custom_0@custom.mozmail.com",
      created_at: "2020-04-09T00:00:00.000Z",
      description: "",
      domain: 2,
      enabled: true,
      block_list_emails: true,
      block_level_one_trackers: true,
      id: 1,
      last_modified_at: "2020-04-09T00:00:00.000Z",
      last_used_at: "2020-04-09T00:00:00.000Z",
      num_blocked: 424242,
      num_forwarded: 0,
      num_replied: 9120,
      num_spam: 0,
      num_level_one_trackers_blocked: 1337,
      mask_type: "custom",
      used_on: "",
    },
  ],
};

export const mockedRealphones: Record<typeof mockIds[number], RealPhoneData> = {
  empty: [],
  onboarding: [],
  some: [
    {
      id: 0,
      number: "+14155552671",
      verification_code: "123456",
      verification_sent_date: "2022-07-27T10:17:29.775Z",
      verified: true,
      verified_date: "2022-07-27T10:18:01.801Z",
      country_code: "US",
    },
  ],
  full: [
    {
      id: 0,
      number: "+14155552671",
      verification_code: "123456",
      verification_sent_date: "2022-07-27T10:17:29.775Z",
      verified: true,
      verified_date: "2022-07-27T10:18:01.801Z",
      country_code: "US",
    },
  ],
};

export const mockedRelaynumbers: Record<
  typeof mockIds[number],
  RelayNumberData
> = {
  empty: [],
  onboarding: [],
  some: [
    {
      id: 0,
      number: "+18089251571",
      location: "Hilo",
      country_code: "US",
      enabled: true,
      remaining_texts: 74,
      remaining_minutes: 49,
      calls_forwarded: 3,
      calls_blocked: 1,
      texts_forwarded: 17,
      texts_blocked: 5,
      calls_and_texts_forwarded: 20,
      calls_and_texts_blocked: 6,
    },
  ],
  full: [
    {
      id: 0,
      number: "+18089251571",
      location: "Hilo",
      country_code: "US",
      enabled: true,
      remaining_texts: 74,
      remaining_minutes: 49,
      calls_forwarded: 3,
      calls_blocked: 1,
      texts_forwarded: 17,
      texts_blocked: 5,
      calls_and_texts_forwarded: 20,
      calls_and_texts_blocked: 6,
    },
  ],
};

export const mockedInboundContacts: Record<
  typeof mockIds[number],
  InboundContactData
> = {
  empty: [],
  onboarding: [],
  some: [
    {
      id: 0,
      relay_number: 150,
      inbound_number: "+18089251571",
      last_inbound_date: "2022-07-27T10:18:01.801Z",
      last_inbound_type: "call",
      num_calls: 45,
      num_calls_blocked: 3,
      num_texts: 13,
      num_texts_blocked: 18,
      blocked: false,
    },
  ],
  full: [
    {
      id: 0,
      relay_number: 150,
      inbound_number: "+18089251571",
      last_inbound_date: "2022-07-27T10:18:01.801Z",
      last_inbound_type: "text",
      num_calls: 45,
      num_calls_blocked: 3,
      num_texts: 13,
      num_texts_blocked: 18,
      blocked: false,
    },
    {
      id: 1,
      relay_number: 150,
      inbound_number: "+18089251571",
      last_inbound_date: new Date(
        Date.now() - 24 * 60 * 60 * 1000
      ).toISOString(),
      last_inbound_type: "text",
      num_calls: 45,
      num_calls_blocked: 3,
      num_texts: 13,
      num_texts_blocked: 18,
      blocked: false,
    },
    {
      id: 2,
      relay_number: 150,
      inbound_number: "+18089251571",
      last_inbound_date: new Date().toISOString(),
      last_inbound_type: "text",
      num_calls: 45,
      num_calls_blocked: 3,
      num_texts: 13,
      num_texts_blocked: 18,
      blocked: false,
    },
  ],
};
