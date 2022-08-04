import test, { expect }  from '../fixtures/basePages'
import { checkForEmailInput, checkForSignInButton, defaultScreenshotOpts } from '../e2eTestUtils/helpers';

// using logged in state outside of describe block will cover state for all tests in file
test.use({ storageState: 'state.json' })
test.describe.skip('Premium Relay - Purchase Premium Flow, Desktop', () => {

  test.beforeEach(async ({ dashboardPage, page }) => {
    await dashboardPage.open()    
    await checkForEmailInput(page)
  });

  test('Verify that the "Upgrade" button redirects correctly,  C1812640, 1808503', async ({ dashboardPage, page }) => {
    await dashboardPage.upgrade()
    expect(page.url()).toContain('/premium/')
  })  
})

test.describe(() => {
  // run this test only on stage as only stage will accept test cards
  test.skip(() => process.env.E2E_TEST_ENV !== 'stage', 'run only on stage');

  test.beforeEach(async ({ dashboardPage, page }) => {
    await dashboardPage.open()
    await checkForEmailInput(page)
  });

  test('Verify that user can purchase the product using a valid CC', async ({ dashboardPage, subscriptionPage, page }) => {

    // TODO: add flow for stage only
  })  
})

test.describe('Premium Relay - Purchase Premium Flow, Desktop - Visual Regression', () => {
  test.skip(({ browserName }) => browserName !== 'firefox', 'firefox only image comparisons!');

  test.beforeEach(async ({ dashboardPage, page }) => {
    await dashboardPage.open()    
    await checkForEmailInput(page)
  });

  test('Verify that the subscription page is displayed correctly, C1553108', async ({ subscriptionPage, dashboardPage, page }) => {
    await dashboardPage.upgradeNow()
    expect(page.url()).toContain('subscriptions')

    await expect(subscriptionPage.paypalButton).toBeVisible()

    await expect(subscriptionPage.productDetails).toHaveScreenshot(
        `${process.env.E2E_TEST_ENV}-productDetails.png`,
        defaultScreenshotOpts
    );
  })
})

