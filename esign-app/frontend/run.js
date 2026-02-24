const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
    try {
        const browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] });
        const page = await browser.newPage();
        await page.setViewport({ width: 1280, height: 800 });

        console.log("Navigating to dashboard...");
        await page.goto('http://localhost:3001', { waitUntil: 'networkidle2' });

        console.log("Logging in...");
        const emailInput = await page.$('input[placeholder="Email Address"]');
        if (emailInput) {
            await page.type('input[placeholder="your@email.com"]', 'admin@esign.com');
            await page.type('input[placeholder="••••••••"]', 'admin123');

            const buttons = await page.$$('button');
            for (let btn of buttons) {
                const text = await page.evaluate(el => el.textContent, btn);
                if (text && text.includes('Sign In')) {
                    await btn.click();
                    break;
                }
            }
            await page.waitForNavigation({ waitUntil: 'networkidle2' });
        }

        await page.screenshot({ path: '/home/azureuser/esign-app/frontend/screenshot_dash.png' });
        console.log("Dashboard loaded, capturing screenshot_dash.png");

        console.log("Looking for a request to click...");
        // find a request row and click it
        const buttons = await page.$$('button');
        for (let btn of buttons) {
            const text = await page.evaluate(el => el.textContent, btn);
            if (text && text.includes('My Requests')) {
                await btn.click();
                break;
            }
        }

        await new Promise(r => setTimeout(r, 2000));

        const row = await page.$('tbody tr');
        if (row) {
            console.log("Clicking request row...");
            await row.click();
            await new Promise(r => setTimeout(r, 1000));

            await page.screenshot({ path: '/home/azureuser/esign-app/frontend/screenshot_req.png' });
            console.log("Request opened, checking for Sign Now...");

            const reqBtns = await page.$$('button');
            let found = false;
            for (let btn of reqBtns) {
                const text = await page.evaluate(el => el.textContent, btn);
                if (text && (text.includes('Sign Now') || text.includes('Sign this document'))) {
                    console.log("Clicking Sign Now...");
                    await btn.click();
                    found = true;
                    break;
                }
                const title = await page.evaluate(el => el.title, btn);
                if (title && title.includes('Sign this document')) {
                    console.log("Clicking Sign Now by title...");
                    await btn.click();
                    found = true;
                    break;
                }
            }

            if (found) {
                await new Promise(r => setTimeout(r, 1000));
                await page.screenshot({ path: '/home/azureuser/esign-app/frontend/screenshot_sign.png' });
                console.log("Captured screenshot_sign.png!");
            } else {
                console.log("No Sign Now button found.");
            }
        } else {
            console.log("No requests found");
        }

        await browser.close();
    } catch (e) {
        console.error(e);
        process.exit(1);
    }
})();
