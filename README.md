# Music AI Project

Sprint 1 implements Spotify authentication with the official Spotify Web API.

## What It Does

After authenticating your Spotify account, the app prints:

- Spotify Login Success
- Display Name
- User ID
- Country
- Product
- Saved Tracks

## Requirements

- Python 3.11+
- Spotify Developer app credentials

## Setup

1. Create or open your app in the Spotify Developer Dashboard.
2. Add this redirect URI to the app settings:

```text
http://127.0.0.1:8888/callback
```

3. Create a `.env` file in the project root:

```env
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the app:

```bash
python main.py
```

The app opens Spotify authorization in your browser. After login, Spotify redirects
back to the local callback server and the terminal prints your account details and
your first 20 saved tracks.

## Project Structure

```text
music_ai/
    spotify/
        auth.py
        client.py
config.py
main.py
requirements.txt
README.md
.gitignore
```

## Scope

This sprint intentionally does not include a database, GPT integration, Streamlit,
or any Spotipy dependency.
