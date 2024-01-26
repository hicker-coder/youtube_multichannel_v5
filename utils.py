import pandas as pd
import re
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse
from datetime import datetime
import requests
import streamlit as st
import base64
import os
import time
from constants import COLUMNS_TO_CONTROL_IN_INPUT

def set_up_driver():

    # Load environment variables
    load_dotenv()

    # Load the service account key JSON file
    credentials = service_account.Credentials.from_service_account_file(
        os.getenv('CREDENTIALS_PATH'),
        scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
    )

    # Build the YouTube API service
    #youtube = build('youtube', 'v3', credentials=credentials, developerKey=os.getenv('API_KEY'))

    # Create a YouTube API client
    youtube = build('youtube', 'v3', credentials=credentials)

    return youtube


def control_columns_in_input(dataframe, columns_to_control):
    """
    Control specified columns in the dataframe for existence and non-empty rows.

    Parameters:
        dataframe (pd.DataFrame): The input dataframe.
        columns_to_control (list): List of column names to control.

    Returns:
        pd.DataFrame: The original dataframe.

    Raises:
        ValueError: If any of the specified columns are not found in the dataframe or are empty.
    """
    # Check if all specified columns exist in the dataframe
    missing_columns = [col for col in columns_to_control if col not in dataframe.columns]

    if missing_columns:
        raise ValueError(f"Columns not found in the dataframe: {', '.join(missing_columns)}")

    # Check if any of the specified columns are empty (contain only NaN values)
    empty_columns = [col for col in columns_to_control if dataframe[col].dropna().empty]

    if empty_columns:
        raise ValueError(f"Columns are empty: {', '.join(empty_columns)}")

    return dataframe

def extract_channel_names(uploaded_file,channel_names):
    if uploaded_file:
        try:
            if uploaded_file is not None:
                # Read the uploaded file into a DataFrame based on its format (Excel or CSV)
                channel_names_df = (
                    pd.read_excel(uploaded_file)
                    if uploaded_file.name.endswith("xlsx")
                    else pd.read_csv(uploaded_file)
                )
                # Control and validate columns in the input DataFrame
                control_columns_in_input(channel_names_df, COLUMNS_TO_CONTROL_IN_INPUT)
                st.success("Channel names file uploaded successfully!")
                # Extract channel usernames from the DataFrame
                channel_names = channel_names_df["Channel Username"].tolist()
            else:
                st.write("Waiting for file upload ... ⌛")
        except Exception as e:
            st.error(f"Error: {e}")

    return channel_names



def create_download_links(username_list, dataframes):
    st.write("Download the scraped data:")
    for username, df in zip(username_list, dataframes):
        output_file = f"{username}_output.xlsx"
        df.to_excel(output_file, index=False)  # Save the DataFrame to an Excel file

        with open(output_file, 'rb') as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            href = f'<a href="data:file/excel;base64,{b64}" download="{os.path.basename(output_file)}" target="_blank"><button style="background-color: green; color: white; padding: 10px 20px; border: none; border-radius: 4px;">Download Excel for {username}</button></a>'
            st.markdown(href, unsafe_allow_html=True)

def create_download_link(file, link_text, file_type):
    with open(file, 'rb') as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:file/excel;base64,{b64}" download="{os.path.basename(file)}" target="_blank"><button style="background-color: green; color: white; padding: 10px 20px; border: none; border-radius: 4px;">{link_text}</button></a>'
        st.markdown(href, unsafe_allow_html=True)

def unshorten_url(url):
    """Return the unshortened version of a URL."""
    try:
        response = requests.head(url, allow_redirects=True)
        return response.url
    except requests.RequestException as e:
        # Log the error and return the original URL
        print(f"Error unshortening URL {url}: {e}")
        return url

def get_channel_id(youtube , channel_name):
    request = youtube.search().list(
        part='snippet',
        type='channel',
        q=channel_name
    )
    response = request.execute()

    if response['items']:
        # Assuming the first search result is the correct one
        channel_id = response['items'][0]['snippet']['channelId']
        return channel_id
    else:
        return "Channel not found"


def format_duration(duration_str):
    # Regular expression to extract hours, minutes, and seconds from the duration string
    duration_pattern = r'PT(\d*H)?(\d*M)?(\d*S)?'
    matches = re.findall(duration_pattern, duration_str)

    if matches:
        hours, minutes, seconds = matches[0]

        # Convert hours, minutes, and seconds to integers
        hours = int(hours[:-1]) if hours else 0
        minutes = int(minutes[:-1]) if minutes else 0
        seconds = int(seconds[:-1]) if seconds else 0

        # Format the duration as HH:MM:SS
        formatted_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return formatted_duration
    else:
        return duration_str

def get_video_ids_published_after(youtube, username, max_results):
    """
    Fetch video IDs for a given YouTube channel username.
    Only include videos published after November 1st, 2023.

    Parameters:
        youtube: The YouTube API client.
        username: The username of the YouTube channel.
        max_results: The maximum number of video IDs to fetch.

    Returns:
        A list of video IDs.
    """

    try:
        # Get the channel ID from the username
        channel_id = get_channel_id(youtube, username)
        if not channel_id:
            raise ValueError(f"No channel found for username: {username}")

        print(f"Channel ID for '{username}': {channel_id}")

        # Set the date to filter videos published after November 1st, 2023
        published_after = "2023-10-30T00:00:00Z"

        # Fetch the videos from the YouTube channel
        channel_response = youtube.search().list(
            channelId=channel_id,
            part='id',
            maxResults=max_results,
            order='date',
            publishedAfter=published_after
        ).execute()

        # Extract video IDs from the response
        video_ids = [item['id']['videoId'] for item in channel_response['items'] if 'videoId' in item['id']]
        print(f"Video IDs list for '{username}': {video_ids}")

        return video_ids

    except Exception as e:
        print(f"Error fetching video IDs for '{username}': {e}")
        return []

def get_video_ids_published_between(youtube, username, max_results):
    """
    Fetch video IDs for a given YouTube channel username.
    Only include videos published between October 1st, 2023, and November 1st, 2023.

    Parameters:
        youtube: The YouTube API client.
        username: The username of the YouTube channel.
        max_results: The maximum number of video IDs to fetch.

    Returns:
        A list of video IDs.
    """

    try:
        # Get the channel ID from the username
        channel_id = get_channel_id(youtube, username)
        if not channel_id:
            raise ValueError(f"No channel found for username: {username}")

        print(f"Channel ID for '{username}': {channel_id}")

        # Set the dates to filter videos published between October 1st and November 1st, 2023
        published_after = "2023-10-01T00:00:00Z"
        published_before = "2023-11-01T00:00:00Z"

        # Fetch the videos from the YouTube channel
        channel_response = youtube.search().list(
            channelId=channel_id,
            part='id',
            maxResults=max_results,
            order='date',
            publishedAfter=published_after,
            publishedBefore=published_before
        ).execute()

        # Extract video IDs from the response
        video_ids = [item['id']['videoId'] for item in channel_response['items'] if 'videoId' in item['id']]
        print(f"Video IDs list for '{username}': {video_ids}")

        return video_ids

    except Exception as e:
        print(f"Error fetching video IDs for '{username}': {e}")
        return []



def get_video_ids(youtube, username, max_results):
    """Fetch video IDs for a given username."""
    try:
        channel_id = get_channel_id(youtube,username)
        print(channel_id)
        channel_response = youtube.search().list(
            channelId=channel_id,
            part='id',
            maxResults=max_results,
            order='date'
        ).execute()

        video_ids = [item['id']['videoId'] for item in channel_response['items'] if 'videoId' in item['id']]
        print('Videos ids list : -------------------------------------------------')
        print(video_ids)
        return video_ids
    except Exception as e:
        print(f"Error fetching video IDs for {username}: {e}")
        return []


def get_video_data_2(youtube, video_ids):
    """Fetch video data and store in DataFrame."""

    # Define the DataFrame with the required columns
    df = pd.DataFrame(columns=[
        'Channel_Name', 'Channel_ID', 'Video_ID','Original_date','Parsed_date','Video_Title', 'Video_URL',
        'Video_Description', 'Views', 'Likes', 'Dislikes', 'Favorite_Count',
        'Comment_Count', 'Tags', 'Original_duration','Parsed_Duration', 'Actual_End_Time',
        'Actual_Start_Time', 'Concurrent_Viewers', 'Scheduled_Start_Time','Comments_Likes',
        'Transcript'
    ])

    for video_id in video_ids:
        # Request to get video details
        video_response = youtube.videos().list(
            part='snippet,contentDetails,liveStreamingDetails,statistics',
            id=video_id
        ).execute()

        if not video_response['items']:
            print(f"No data found for video ID {video_id}")
            continue

        video_details = video_response['items'][0]

        # Extracting details from various parts of the response
        snippet = video_details.get('snippet', {})
        content_details = video_details.get('contentDetails', {})
        live_details = video_details.get('liveStreamingDetails', {})
        statistics = video_details.get('statistics', {})

        upload_date_original = snippet['publishedAt']
        # Convert 'publishedAt' to a datetime object
        upload_date_parsed = datetime.strptime(upload_date_original, '%Y-%m-%dT%H:%M:%SZ')

        # Extract video elements
        channel_name = snippet.get('channelTitle', '')
        channel_id = snippet.get('channelId', '')
        video_title = snippet.get('title', '')
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_description = snippet.get('description', '')
        views = statistics.get('viewCount', 'N/A')
        likes = statistics.get('likeCount', 'N/A')
        dislikes = statistics.get('dislikeCount', 'N/A')
        favorite_count = statistics.get('favoriteCount', 'N/A')
        comment_count = statistics.get('commentCount', 'N/A')
        tags = snippet.get('tags', [])
        duration = format_duration(content_details.get('duration', None))
        actual_end_time = live_details.get('actualEndTime', None)
        actual_start_time = live_details.get('actualStartTime', None)
        concurrent_viewers = live_details.get('concurrentViewers', None)
        scheduled_start_time = live_details.get('scheduledStartTime', None)

        try :
            comments_and_likes = {}
            next_page_token = ''

            while True:
                comments_response = youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    pageToken=next_page_token,
                    maxResults=100
                ).execute()

                for item in comments_response['items']:
                    comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    comment_likes = int(item['snippet']['topLevelComment']['snippet']['likeCount'])
                    comments_and_likes[comment] = comment_likes

                if 'nextPageToken' in comments_response:
                    next_page_token = comments_response['nextPageToken']
                else:
                    break
        except:
            comment = 'Videos has disabled comments'
            comment_likes = 0
            comments_and_likes[comment] = 0

        # transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt'])
            print(transcript)
            texts = [item['text'] for item in transcript]
        except Exception as e:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                print(transcript)
                texts = [item['text'] for item in transcript]
            except Exception as e:
                transcript = 'No Transcript Found neither in Portuguese or English'
                texts = transcript

        # Append to the DataFrame
        df = df._append({
            'Channel_Name': channel_name,
            'Channel_ID': channel_id,
            'Video_ID':video_id,
            'Video_Title': video_title,
            'Original_date':upload_date_original,
            'Parsed_date':upload_date_parsed,
            'Video_URL': video_url,
            'Video_Description': video_description,
            'Views': views,
            'Likes': likes,
            'Dislikes': dislikes,
            'Favorite_Count': favorite_count,
            'Comment_Count': comment_count,
            'Tags': tags,
            'Original_duration':duration,
            'Parsed_Duration': format_duration(duration),
            'Actual_End_Time': actual_end_time,
            'Actual_Start_Time': actual_start_time,
            'Concurrent_Viewers': concurrent_viewers,
            'Scheduled_Start_Time': scheduled_start_time,
            'Comments_Likes':comments_and_likes,
            'Transcript':texts
        }, ignore_index=True)

    return df

def get_video_data(youtube, video_ids):
    """Fetch video data, comments, likes, transcripts, etc. and store in DataFrame."""
    df = pd.DataFrame(columns=['Channel_Name', 'Video_URL', 'Video_Description', 'Views', 'Comments', 'Likes', 'URLs', 'tags', 'Transcript'])


    for video_id in video_ids:
        video_response = youtube.videos().list(
            part='statistics,snippet',
            id=video_id
        ).execute()

        # print(video_response)
        print('Exiting to control the video response ... ')

        video_statistics = video_response['items'][0]['statistics']
        video_snippet = video_response['items'][0]['snippet']
        upload_date = video_snippet['publishedAt']
        # Convert 'publishedAt' to a datetime object
        upload_date = datetime.strptime(upload_date, '%Y-%m-%dT%H:%M:%SZ')
        print(upload_date)

        try:
            likes = int(video_statistics['likeCount'])
        except KeyError:
            likes = ''

        try:
            views = int(video_statistics['viewCount'])
        except KeyError:
            views = ''

        #likes = int(video_statistics['likeCount'])
        #views = int(video_statistics['viewCount'])
        description = video_snippet['description']
        urls_in_description = re.findall(r'(https?://\S+)', description)
        # urls_in_description = [unshorten_url(url) for url in urls_in_description]
        # company_names = [urlparse(url).netloc.split('.')[1] for url in urls_in_description]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        #channel_name = video_snippet['channelTitle']

        try:
            channel_name = video_snippet['channelTitle']
        except KeyError:
            channel_name = ''

        print('video likes :')
        print(likes)
        print('video url')
        print(video_url)

        try :
            comments_and_likes = {}
            next_page_token = ''

            while True:
                comments_response = youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    pageToken=next_page_token,
                    maxResults=30
                ).execute()

                for item in comments_response['items']:
                    comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    comment_likes = int(item['snippet']['topLevelComment']['snippet']['likeCount'])
                    comments_and_likes[comment] = comment_likes

                if 'nextPageToken' in comments_response:
                    next_page_token = comments_response['nextPageToken']
                else:
                    break
        except:
            comment = 'Videos has disabled comments'
            comment_likes = 0
            comments_and_likes[comment] = 0

        # transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt'])
            #print(transcript)
            texts = [item['text'] for item in transcript]
        except Exception as e:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                #print(transcript)
                texts = [item['text'] for item in transcript]
            except Exception as e:
                transcript = 'No Transcript Found neither in Portuguese or English'
                texts = transcript


        # Now you can use the transcript variable as needed

        #print('Transcript : ')
        #print(transcript)
        #texts = [item['text'] for item in transcript]

        df = df._append({
            'Channel_Name': channel_name,
            'Video_URL': video_url,
            'Upload_date': upload_date,
            'Video_Description': description,
            'Views': views,
            'Comments': comments_and_likes,
            'Likes': likes,
            'URLs': urls_in_description,
            # 'tags': company_names,
            'Transcript': texts
        }, ignore_index=True)


    return df



def extract_video_data(youtube, username, max_results, progress, progress_message):
    """Fetch and save YouTube channel data based on the provided username."""

    # Get video IDs
    video_ids = get_video_ids_published_between(youtube, username, max_results)
    print(video_ids)


    # Update progress and message
    progress.progress(25)
    progress_message.text(f"Completed: Getting video IDs for {username} (25%)")
    time.sleep(1)  # Simulated delay

    # Fetch video data and store in DataFrame
    df = get_video_data_2(youtube, video_ids)

    # Update progress and message
    progress.progress(75)
    progress_message.text(f"Completed: Fetching video data for {username} (75%)")
    time.sleep(1)  # Simulated delay

    # Create a unique output file name for each channel
    output_file = f"{username}_output.csv"
    print(output_file)
    # Remove tabs and newline characters from the output_file string
    output_file = output_file.replace('\t', '').replace('\n', '')

    print(df.head(10))


    # Export DataFrame to Excel file
    df.to_csv(output_file, index=False)

    # Complete progress and message
    progress.progress(100)
    progress_message.text(f"Completed: Exporting data to {output_file} (100%)")

    return df

