# BLYRIC

BLYRIC, a bot that tweets a song lyric every night.

Follow on Twitter: [@blyric_](https://twitter.com/blyric_)

[![](images/wallpaper.jpeg)](https://twitter.com/blyric_)

# Overview

BLYRIC is a Twitter bot that tweets a song quote every night. Users can request new albums to be registered and compose the lyrics base.

Here's an example of a daily tweet:

<p align="center">
    <img src="images/tweet_example.png" width="50%">
</p>


You can mention BLYRIC on a tweet to request an album to compose the lyrics base. You can do it just mentioning our username and writing the album name in the same tweet, just like this:

<p align="center">
    <img src="images/album_request_example.png" width="50%">
</p>

Once tweeted, BLYRIC will search in [Genius website](https://genius.com/) if there is an album like this tweet. If so, it will register this album into the database, and a lyric of this album can be sorted.  
When registered, BLYRIC also tweets the new album that was registered, like this:

<p align="center">
    <img src="images/new_album_example.png" width="50%">
</p>

# Operation

BLYRIC is coded in Python 3.9.5, and works with Twitter API and Genius API.

Its lyrics data is stored in a Google Sheets, being read and updated by Google Sheets API

It is hosted on [Heroku](https://dashboard.heroku.com), for free.

BLYRIC executes some steps everyday:

- Connect to Twitter API
- Conncet to Genius API
- Import database
- Tweets the daily lyric
- Check the mentions and - if requested - register the new albums on the database
- Send e-mail report
