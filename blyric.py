
from   yaml         import load, SafeLoader
from   lyricsgenius import Genius
import tweepy

from time import sleep

from googleapiclient.discovery import build

import gspread
import pandas as pd
from   re           import compile

from random   import choice

from smtplib       import SMTP_SSL
from email.message import EmailMessage
from datetime      import date

report = {
    "youtube_api_connection"     : 0,
    "twitter_api_connection"     : 0,
    "genius_api_connection"      : 0,

    "get_actual_playlist"        : 0,
    "update_playlist_history"    : 0,

    "get_actual_playlist_lyrics" : 0,
    "update_actual_lyrics"       : 0,

    "tweet"                      : 0
}

def main():

    while True:

        clean_report()

        youtube = connect_to_youtube()
        genius  = connect_to_genius()
        bot     = connect_to_twitter()

        actual_playlist = get_actual_playlist(youtube)
        update_playlist_history(actual_playlist)
        actual_playlist_lyrics = get_actual_playlist_lyrics(actual_playlist, genius)
        update_actual_lyrics(actual_playlist_lyrics)

        tweet_lyric(bot, actual_playlist_lyrics)

        send_email_report()

        print(report)

        sleep(60*60*24)

def clean_report():

    for key in report.keys():
        report[key] = 0

def get_credentials(credentials_filepath = "credentials.yaml"):

    try:
        credentials = load(
            stream = open(credentials_filepath, encoding = "utf8"),
            Loader = SafeLoader
        )
    except:
        credentials = None

    return credentials

def connect_to_youtube():

    print("Connecting to YouTube")

    try:
        credentials = get_credentials()
        youtube = build("youtube", "v3", developerKey = credentials["youtube_api_key"])
        report["youtube_api_connection"] = 1
    except:
        youtube = None

    return youtube

def connect_to_twitter():

    print("Connecting to Twitter")

    try:
        credentials = get_credentials()

        auth = tweepy.OAuthHandler(
            consumer_key    = credentials["twitter_consumer_api_key"],
            consumer_secret = credentials["twitter_consumer_api_key_secret"]
        )
        auth.set_access_token(
            key    = credentials["twitter_access_token"],
            secret = credentials["twitter_access_token_secret"]
        )
        bot = tweepy.API(auth)

        report["twitter_api_connection"] = 1
    except:
        bot = None

    return bot

def connect_to_genius():

    print("Connecting to Genius")

    try:
        credentials = get_credentials()

        genius = Genius(
            access_token = credentials["genius_access_token"],
            verbose = False
        )
        
        report["genius_api_connection"] = 1
    except:
        genius = None

    return genius

def get_actual_playlist(youtube):

    print("Getting actual playlist songs")

    try:

        credentials = get_credentials()

        request = youtube.playlistItems().list(
            part = ["id", "snippet", "status"],
            playlistId = credentials["playlist_id"],
            maxResults = 50
        )
        response = request.execute()

        song_names = []
        song_channels = []
        song_links = []

        for video in response["items"]:
            song_name = video["snippet"]["title"]
            song_channel = video["snippet"]["videoOwnerChannelTitle"]
            song_link = video["snippet"]["resourceId"]["videoId"]

            song_names.append(song_name)
            song_channels.append(song_channel)
            song_links.append(song_link)

        playlist = pd.DataFrame({
            "song_name": song_names,
            "song_channel": song_channels,
            "song_id": song_links
        })

        report["get_actual_playlist"] = 1

    except:
        playlist = None

    return playlist

def update_playlist_history(actual_playlist):

    print("Updating playlist history")

    try:
        credentials = get_credentials()

        actual_playlist["grass_date"] = str(date.today())

        sh = gspread.\
            service_account(filename = "blyric-9f2cb3602446.json").\
            open_by_key(credentials["google_sheet_id"]).\
            worksheet("personal_playlist_history")

        sh.insert_rows(actual_playlist.fillna('').values.tolist(), 2)

        report["update_playlist_history"] = 1
    except:
        None

def clean_lyric(lyric):

    try:
        verses = lyric.split("\n")
        r = compile("(Chorus)|(])|(Verse \d)|(Embed)")
        return [verse.strip() for verse in verses if not r.search(verse) and verse != ""]
    except:
        return lyric

def get_actual_playlist_lyrics(actual_playlist, genius):
    
    print("Getting the lyrics")

    try:
        song_names = []
        song_artists = []
        song_lyrics = []

        for i in range(len(actual_playlist)):
            song = genius.search_song(" - ".join(actual_playlist.iloc[i, :2].values).split(" - Topic")[0])
            if song is not None:
                song_name = song.title
                song_artist = song.artist
                song_lyric = song.lyrics

                song_names.append(song_name)
                song_artists.append(song_artist)
                song_lyrics.append(song_lyric)

        actual_playlist_lyrics = pd.DataFrame({
            "song_name": song_names,
            "artist": song_artists,
            "lyrics": [clean_lyric(full_lyric) for full_lyric in song_lyrics]
        }).explode("lyrics")

        report["get_actual_playlist_lyrics"] = 1
    except:
        actual_playlist_lyrics = None

    return actual_playlist_lyrics

def update_actual_lyrics(actual_playlist_lyrics):

    print("Updating actual lyrics")

    try:
        credentials = get_credentials()

        sh = gspread.\
            service_account(filename = "blyric-9f2cb3602446.json").\
            open_by_key(credentials["google_sheet_id"]).\
            worksheet("lyrics")

        sh.clear()
        sh.update(f"A1:F{len(actual_playlist_lyrics.fillna('').T.reset_index().T)}", actual_playlist_lyrics.fillna("").T.reset_index().T.values.tolist())

        report["update_actual_lyrics"] = 1
    except:
        None

def pick_a_lyric(actual_playlist_lyrics):

    print("Picking a lyric: ", end = "")

    try:
        song_choice = choice(actual_playlist_lyrics["song_name"].unique().tolist())
        lyric = actual_playlist_lyrics\
                [actual_playlist_lyrics["song_name"] == song_choice].\
                sample().\
                to_dict("records")[0]
        print(f'{lyric["artist"]} - {lyric["song_name"]}')
    except:
        lyric = None

    return lyric

def tweet_lyric(bot, df):

    print("Tweeting lyric")

    try:
        lyric = pick_a_lyric(df)

        tweet = f'{lyric["lyrics"]}\n- #{lyric["artist"].replace(" ", "")}, {lyric["song_name"]}'
        #bot.update_status(tweet)

        report["tweet"] = tweet
    except:
        None

def send_email_report():

    credentials = get_credentials()

    msg = EmailMessage()

    msg["Subject"] = f"BLYRIC Twitter Bot - Report [{str(date.today())}]"
    msg["From"]    = credentials["email_address"]
    msg["To"]      = credentials["email_address"]

    msg.add_alternative(f'''\
    <html lang="en">
        <body>
            <p>
            Daily tweet:
            <br>
            {report["tweet"] if report["tweet"] != 0 else "Error"}
            </p>

            <table style="line-height: 35px; width: 500px; border-collapse: collapse; font-family: Arial;">
                <tr style="border-bottom: 1px solid black;">
                    <th>Task</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>YouTube connection</td>
                    <td>{"Success" if report["youtube_api_connection"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Twitter connection</td>
                    <td>{"Success" if report["twitter_api_connection"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Genius connection</td>
                    <td>{"Success" if report["genius_api_connection"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Data import: actual playlist</td>
                    <td>{"Success" if report["get_actual_playlist"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Data export: actual playlist</td>
                    <td>{"Success" if report["update_playlist_history"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Data import: lyrics</td>
                    <td>{"Success" if report["get_actual_playlist_lyrics"] == 1 else "Not done"}</td>
                </tr>
                <tr>
                    <td>Data export: lyrics</td>
                    <td>{"Success" if report["update_actual_lyrics"] == 1 else "Not done"}</td>
                </tr>
            </table>

            <p>Regards, <a href="https://twitter.com/{credentials["twitter_username"]}">BLYRIC</a>.</p>
        </body>
    </html>
    ''',
    subtype = "html"
    )

    with SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(credentials["email_address"], credentials["email_app_password"])
        smtp.send_message(msg)

if __name__ == "__main__":
    main()
