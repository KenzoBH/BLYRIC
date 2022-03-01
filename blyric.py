
from   yaml         import load, SafeLoader, dump
from   lyricsgenius import Genius
import tweepy

from time import sleep

import gspread
from gspread_dataframe import get_as_dataframe
import pandas as pd
from   re           import compile

from random   import choice
from requests import get
from os       import remove

from smtplib       import SMTP_SSL
from email.message import EmailMessage
from datetime      import date

report = {
    "twitter_api_connection" : 0,
    "genius_api_connection"  : 0,

    "data_import"            : 0,

    "tweet"                  : 0,

    "new_mentions"           : [],
    "new_albums_to_tweet"    : 0,
    "tweeted_new_albums"     : 0,

    "data_export"            : 0
}

def main():

    while True:

        sleep(60*5)

        clean_report()

        bot    = connect_to_twitter()
        genius = connect_to_genius()

        df = import_data()

        tweet_lyric(bot, df)
        check_mentions(bot, genius, df)

        send_email_report()

        print(report)

def clean_report():

    for key in report.keys():
        report[key] = 0
    report["new_mentions"] = []

def get_credentials(credentials_filepath = "credentials.yaml"):

    try:
        credentials = load(
            stream = open(credentials_filepath, encoding = "utf8"),
            Loader = SafeLoader
        )
    except:
        credentials = None

    return credentials

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

def import_data():

    print("Importing dataset")    

    try:
        credentials = get_credentials()

        sh = gspread.\
            service_account(filename = "blyric-9f2cb3602446.json").\
            open_by_key(credentials["google_sheet_id"]).\
            worksheet("lyrics")
        df = get_as_dataframe(sh)
        
        report["data_import"] = 1
    except:
        df = None
    
    return df

def pick_a_lyric(df):

    print("Picking a lyric: ", end = "")

    try:
        album = choice(df["album_name"].unique().tolist())
        lyric = df\
                [df["album_name"] == album].\
                sample().\
                to_dict("records")[0]
        print(f'{lyric["artist_name"]} - {lyric["song"]}')
    except:
        lyric = None

    return lyric

def tweet_lyric(bot, df):

    print("Tweeting lyric")

    try:
        lyric = pick_a_lyric(df)

        tweet = f'{lyric["lyrics"]}\n- {lyric["artist_name"]}, {lyric["song"]}\n({lyric["album_name"]})'
        bot.update_status(tweet)

        report["tweet"] = {
            "tweet"        : tweet,
            "quote"        : lyric["lyrics"],
            "song"         : lyric["song"],
            "artist"       : lyric["artist_name"],
            "album"        : lyric["album_name"]
        }
    except:
        None

def check_mentions(bot, genius, df):

    print("Checking new mentions: ", end = "")

    try:

        credentials = get_credentials()

        mentions = bot.mentions_timeline(since_id = credentials["last_mention_read"])
        report["new_mentions"] = [
            {
                "tweet_id"  : mention.id,
                "tweet"     : mention.text,
                "user"      : mention.user.screen_name,
                "user_pic"  : mention.user.profile_image_url,
                "new_album" : None,
                "album_url" : None,
            }
            for mention in mentions
        ]
        print(len(mentions))

        if len(mentions) != 0:

            for i in range(len(mentions)):

                mention = mentions[i].text.upper().replace(f'@{credentials["twitter_username"].upper()}', "").strip()
                album = get_album_from_text(genius, mention)

                if album is not None and is_new_album(df, album.id):
                    register_album(df, album)
                    like_tweet(bot, mentions[i])
                    tweet_new_album(bot, album)
                    
                    x = pd.DataFrame(report["new_mentions"])
                    x.loc[x["tweet_id"] == mentions[i].id, "new_album"] = album.name
                    x.loc[x["tweet_id"] == mentions[i].id, "album_url"] = album.url
                    report["new_mentions"] = x.to_dict("records")
                    report["new_albums_to_tweet"] += 1

            update_last_mention_read(mentions[0].id)

    except:
        None

def update_last_mention_read(last_mention_read_id):
    
    try:
        credentials = get_credentials()

        credentials["last_mention_read"] = last_mention_read_id
        with open(r"credentials.yaml", "w") as file:
            documents = dump(credentials, file)
    except:
        None

def get_album_from_text(genius, tweet):

    try:

        print(f"\tLooking for any album in this tweet: '{tweet}'")

        album = genius.search_album(tweet)

        if album is None or len(genius.artist_leaderboard(album.artist.id)["leaderboard"]) < 10:
            print("\t\tAlbum not found")
            return None    
        else:
            print(f'\t\tAlbum found: {album.name}')
            return album

    except:
        return None

def is_new_album(df, id_):

    try:
        if len(df[df["album_id"].isin([id_])]) == 0:
            print("\t\tAlbum not registered yet")
            return True
        else:
            print("\t\tAlbum already registered")
            return False
    except:
        print("\t\tError checking if album is registered")
        return False

def clean_lyric(lyric):

    try:
        verses = lyric.split("\n")
        r = compile("(Chorus)|(])|(Verse \d)|(Embed)")
        return [verse.strip() for verse in verses if not r.search(verse) and verse != ""]
    except:
        return lyric

def register_album(df, album):

    print(f"\t\tRegistering album: {album.name}")

    try:
        new_album = pd.DataFrame({
            "artist_name" : album.artist.name.replace("\u200b", ""),
            "artist_id"   : album.artist.id,
            "album_name"  : album.name,
            "album_id"    : album.id,
            "song"        : [track.song.title for track in album.tracks],
            "lyrics"      : [clean_lyric(track.song.lyrics) for track in album.tracks]
        }).explode("lyrics")
        new_df = df.append(new_album)
    except:
        new_df = df

    print(new_df.head())
    export_data(new_df)

    return new_df

def tweet_new_album(bot, album):

    try:
        tweet = f"""{album.artist.name}, {album.name} ({album.release_date_components.year})\n"""
        for i in range(len(album.tracks)):
            tweet += f"\n{i + 1}. {album.tracks[i].song.title}"
            if len(tweet) > 240:
                tweet += "\n[...]"
                break

        files = [album.cover_art_url, album.artist.image_url]
        filenames = []

        media_ids = []

        for i in range(len(files)):

            if files[i][-3:] != "gif":
                request = get(files[i], stream = True)

                filename = f'{"album_cover" if i == 0 else "artist_cover"}.jpg'
                filenames.append(filename)

                if request.status_code == 200:
                    with open(filename, "wb") as image:
                        for chunk in request:
                            image.write(chunk)

                res = bot.media_upload(filename)
                media_ids.append(res.media_id)

        bot.update_status(
            status = tweet,
            media_ids = media_ids
        )

        for filename in filenames:
            remove(filename)

        report["tweeted_new_albums"] += 1

    except:
        None

def export_data(df):
    
    print("Exporting data")

    try:
        credentials = get_credentials()

        sh = gspread.\
            service_account(filename = "blyric-9f2cb3602446.json").\
            open_by_key(credentials["google_sheet_id"]).\
            worksheet("lyrics")

        sh.update(f"A1:F{len(df.T.reset_index().T)}", df.T.reset_index().T.values.tolist())

        report["data_export"] = 1
    except:
        None

def like_tweet(bot, tweet):

    try:
        bot.create_favorite(tweet.id)
    except:
        None

def send_email_report():

    mentions_table = ""
    if len(report["new_mentions"]) != 0:
        mentions_table += '''
        <table style="line-height: 35px; width: 500px; border-collapse: collapse; font-family: Arial;">
            <tr style="border-bottom: 1px solid black;">
                <th>User picture</th>
                <th>User</th>
                <th>Mention tweet</th>
                <th>Album registered</th>
            </tr>
        '''
        for mention in report["new_mentions"]:
            mentions_table += f"""
            <tr>
                <td><img src="{mention["user_pic"]}" alt=""></td>
                <td><a href="https://twitter.com/{mention["user"]}">@{mention["user"]}</a></td>
                <td><a href="https://twitter.com/{mention["user"]}/status/{mention["tweet_id"]}">{mention["tweet"]}</a></td>
                <td><a href="{mention["album_url"]}">{mention["new_album"]}</a></td>
            </tr>
            """
        mentions_table += "</table>"

    credentials = get_credentials()

    msg = EmailMessage()

    msg["Subject"] = f"Blyric Twitter Bot - Report [{str(date.today())}]"
    msg["From"]    = credentials["email_address"]
    msg["To"]      = credentials["email_address"]

    msg.add_alternative(f'''\
    <html lang="en">
        <body>
            <p>
            Daily tweet:
            <br>
            {report["tweet"]["tweet"] if report["tweet"] != 0 else "Error"}
            </p>

            <table style="line-height: 35px; width: 500px; border-collapse: collapse; font-family: Arial;">
                <tr style="border-bottom: 1px solid black;">
                    <th>Task</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Twitter connection</td>
                    <td>{"Success" if report["twitter_api_connection"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Genius collection</td>
                    <td>{"Success" if report["genius_api_connection"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>Data import</td>
                    <td>{"Success" if report["data_import"] == 1 else "Fail"}</td>
                </tr>
                <tr>
                    <td>New mentions</td>
                    <td>{len(report["new_mentions"])}</td>
                </tr>
                <tr>
                    <td>Albums requested</td>
                    <td>{report["new_albums_to_tweet"]}</td>
                </tr>
                <tr>
                    <td>New albums registered</td>
                    <td>{report["tweeted_new_albums"]}</td>
                </tr>
                <tr>
                    <td>Data export</td>
                    <td>{"Success" if report["data_export"] == 1 else "Not done"}</td>
                </tr>
            </table>

            {mentions_table}

            <p>Regards, <a href="https://twitter.com/{credentials["twitter_username"]}">Blyric</a>.</p>
        </body>
    </html>
    ''',
    subtype = "html"
    )

    with SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(credentials["email_address"], credentials["email_password"])
        smtp.send_message(msg)

if __name__ == "__main__":
    main()
