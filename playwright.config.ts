import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    use: {
        baseURL: 'http://localhost:3000',
        trace: 'on-first-retry',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
    webServer: {
        command: 'npm run start',
        env: {
            CODEX_E2E_AUTH_BYPASS: 'true',
            NEXT_PUBLIC_CASE_DETAIL_POLL_INTERVAL_MS: '100',
            NEXT_PUBLIC_CASE_DETAIL_STALE_FINGERPRINT_MS: '300',
            NEXT_PUBLIC_CASE_DETAIL_STALE_TOTAL_WAIT_MS: '900',
        },
        url: 'http://localhost:3000',
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
    },
});
