import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Directory to save screenshots
screenshots_save_dir = "/Users/gayatrikrishnakumar/desktop/Screenshots_Run"
os.makedirs(screenshots_save_dir, exist_ok=True)


def init_webdriver():
    """Initialize Chrome WebDriver with headless option"""
    options = Options()
    options.add_argument("--headless")  # Run browser in headless mode (without UI)
    options.add_argument("--disable-gpu")
    options.binary_location = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"  # Path to Chrome on macOS
    )
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def capture_screenshots(driver, url, save_dir):
    """Capture screenshots by scrolling through a webpage"""
    driver.get(url)
    driver.set_window_size(1920, 1080)

    total_height = driver.execute_script("return document.body.scrollHeight")
    scrolled_height = 0
    screenshot_index = 1

    while scrolled_height < total_height:
        # Scroll down by the height of the window
        driver.execute_script(f"window.scrollTo(0, {scrolled_height});")
        time.sleep(2)  # Adjust based on page load

        # Save the screenshot
        file_path = os.path.join(save_dir, f"screenshot_{screenshot_index}.png")
        driver.save_screenshot(file_path)
        print(f"Screenshot saved: {file_path}")

        screenshot_index += 1
        scrolled_height += 1080

        # Update total_height in case the page dynamically loads more content
        new_height = driver.execute_script("return document.body.scrollHeight")
        total_height = max(new_height, total_height)


def login(driver, url, username_inp, password_inp):
    """Log in to a website using email and password"""
    driver.get(url)
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    # Wait for email and password input fields
    email_input = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
    )
    email_input.send_keys(username_inp)

    password_input = WebDriverWait(driver, 30).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
    )
    password_input.send_keys(password_inp)

    # Find and click the submit button
    submit_button = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
    )
    submit_button.click()

    # Wait for the home page or an element specific to a successful login
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "unique_home_page_element"))
    )  # Example element


def main():
    """Main function to run the login and screenshot capture"""
    driver = init_webdriver()
    try:
        login_url = "https://social-sandbox.com/auth/sign_in"
        home_url = "https://social-sandbox.com/home"
        username = "austinmw89+user0001@gmail.com"
        password = "9f5fcfd16622a42a2459c297f658a7d5"

        # Log in to the website
        login(driver, login_url, username, password)
        print("Login Successful")

        # Capture screenshots after login
        capture_screenshots(driver, home_url, screenshots_save_dir)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
