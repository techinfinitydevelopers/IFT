import asyncio
from pyppeteer import launch
import os

async def html_to_pdf():
    # Get the absolute path to the HTML file
    html_path = os.path.abspath('EVALUATION_ENGINE_DOC.html')
    pdf_path = os.path.abspath('EVALUATION_ENGINE_DOC.pdf')
    
    print(f"Converting: {html_path}")
    print(f"Output: {pdf_path}")
    
    # Launch browser
    browser = await launch(headless=True)
    page = await browser.newPage()
    
    # Navigate to the HTML file
    await page.goto(f'file:///{html_path}', waitUntil='networkidle0')
    
    # Generate PDF with background printing enabled
    await page.pdf({
        'path': pdf_path,
        'format': 'A4',
        'printBackground': True,  # This preserves the black background
        'margin': {
            'top': '20px',
            'right': '20px',
            'bottom': '20px',
            'left': '20px'
        }
    })
    
    await browser.close()
    print(f"PDF generated successfully: {pdf_path}")

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(html_to_pdf())
