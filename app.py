# Import necessary libraries and modules
import streamlit as st  # Import Streamlit for creating the web app interface
import os  # Import os for working with the file system
from dotenv import load_dotenv  # Import dotenv for loading environment variables
from constants import MAX_RESULTS, COLUMNS_TO_CONTROL_IN_INPUT  # Import constants from a separate module
from utils import (
    set_up_driver,
    extract_channel_names,
    create_download_links,
    extract_video_data,
)  # Import functions from a separate utils module
from styles import NAVBAR

# Load environment variables from a .env file
load_dotenv()

# Define the main function of the web app
def app():
    # Set up a Selenium driver for YouTube
    youtube = set_up_driver()

    # Set the title of the web app
    st.title("Infomineo YouTube Data Scraper")

    # Initialize a list to store channel usernames
    global channel_names
    channel_names = []

    # Get user input for channel usernames by uploading an Excel or CSV file
    uploaded_file = st.file_uploader(
        "Upload an Excel file with channel usernames (Excel or CSV)",
        type=["xlsx", "xls"],
    )

    channel_names = extract_channel_names(uploaded_file,channel_names)
    print(channel_names)

    # Get user input for the maximum number of videos to fetch
    max_results = st.number_input(
        "Enter the maximum number of videos to fetch:",
        min_value=1,
        max_value=1000,
        value=MAX_RESULTS,
        step=1,
    )

    # Create a button to start scraping data for all channels
    if st.button('Extract Data', channel_names):
        if not channel_names:
            st.warning("No channel names provided. Please upload a file containing channel names.")
            return

        # Create a progress bar and a placeholder for progress messages
        progress = st.progress(0)
        progress_message = st.empty()

        dataframes = []  # Initialize a list to store DataFrames

        # Iterate through each channel username and scrape data
        for username in channel_names:
            print('Here is teh USERAM')
            print(username)
            st.subheader(f"Scraping data for channel: {username}")
            df = extract_video_data(youtube, username, max_results, progress, progress_message)
            dataframes.append(df)  # Append the DataFrame to the list

        # Create download links for each channel's data
        create_download_links(channel_names, dataframes)

        # Create a custom navbar with links
        navbar = NAVBAR
        st.markdown(navbar, unsafe_allow_html=True)


# Check if the script is being run directly
if __name__ == "__main__":
    OUTPUT_DIRECTORY = "output"  # Directory to store output Excel files
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)  # Create the output directory if it doesn't exist
    app()  # Call the main web app function
