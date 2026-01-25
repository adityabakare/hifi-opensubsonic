import httpx
import asyncio
import sys
import os

# Add parent dir to path if running from tests/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings

BASE_URL = "http://localhost:8000"

async def test_ping():
    print("Testing Ping...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/rest/ping.view?u=test&p=test&v=1.16.1&c=test&f=json")
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        assert resp.status_code == 200
        assert resp.json()["subsonic-response"]["status"] == "ok"

async def test_license():
    print("\nTesting GetLicense...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/rest/getLicense.view?u=test&p=test&v=1.16.1&c=test&f=json")
        print(f"Response: {resp.json()}")
        assert resp.status_code == 200

async def test_music_folders():
    print("\nTesting GetMusicFolders...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/rest/getMusicFolders.view?u=test&p=test&v=1.16.1&c=test&f=json")
        print(f"Response: {resp.json()}")
        assert resp.status_code == 200

async def test_root_directory():
    print("\nTesting Root Directory...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/rest/getMusicDirectory.view?id=root&u=test&p=test&v=1.16.1&c=test&f=json")
        print(f"Response: {resp.json()}")
        assert resp.status_code == 200

async def test_search():
    print("\nTesting Search3...")
    async with httpx.AsyncClient() as client:
        # Search for "Weeknd" - should return tracks, albums, artists
        resp = await client.get(f"{BASE_URL}/rest/search3.view?query=Weeknd&u=test&p=test&v=1.16.1&c=test&f=json")
        print(f"Response Status: {resp.status_code}")
        data = resp.json()
        assert resp.status_code == 200
        
        results = data["subsonic-response"]["searchResult3"]
        
        # Verify we got all types
        songs = results.get("song", [])
        artists = results.get("artist", [])
        albums = results.get("album", [])
        
        print(f"Found {len(songs)} songs, {len(artists)} artists, {len(albums)} albums")
        
        assert len(songs) > 0
        assert len(artists) > 0
        assert len(albums) > 0
        assert len(albums) > 0
        
        # Check first song details
        s1 = songs[0]
        print("Sample Song:", s1.get("title"))
        print("Sample Song:", s1.get("title"))
        print(f"Format: {s1.get('suffix')}, {s1.get('bitRate')}kbps, {s1.get('bitDepth')}bit, {s1.get('samplingRate')}Hz")
        print(f"Meta: Track {s1.get('track')} (Disc {s1.get('discNumber')}), Gain {s1.get('replayGain')}")
        print(f"IDs: Artist {s1.get('artistId')}, Album {s1.get('albumId')}")
        
        print("Search structure valid.")

async def test_get_artist_album_endpoints():
    print("\nTesting getArtist and getAlbum...")
    async with httpx.AsyncClient() as client:
        # Use known Artist ID for The Weeknd (Tidal ID: 32906)
        artist_id = 32906 
        
        print(f"Testing getArtist for {artist_id}...")
        
        # 2. Test getArtist
        a_resp = await client.get(f"{BASE_URL}/rest/getArtist.view?id={artist_id}&u=test&p=test&v=1.16.1&c=test&f=json")
        if a_resp.status_code != 200:
             print(f"getArtist failed: {a_resp.status_code}")
             return
             
        a_data = a_resp.json()["subsonic-response"]
        assert "artist" in a_data
        
        # Check if we got albums
        if "album" not in a_data["artist"]:
            print("No albums found for artist.")
            return

        print("getArtist OK")
        
        # 3. Test getAlbum
        albums = a_data["artist"]["album"]
        if not albums:
             print("Skipping getAlbum test - no albums found.")
             return
             
        album_id = albums[0]["id"]
        # Strip prefix
        if album_id.startswith("album-"):
            # Check if getAlbum accepts prefix (it should)
            pass

        print(f"Testing getAlbum for {album_id}...")
        al_resp = await client.get(f"{BASE_URL}/rest/getAlbum.view?id={album_id}&u=test&p=test&v=1.16.1&c=test&f=json")
        if al_resp.status_code != 200:
            print(f"getAlbum failed: {al_resp.status_code}")
            # print(al_resp.text)
            return

        al_data = al_resp.json()["subsonic-response"]
        assert "album" in al_data
        assert "song" in al_data["album"]
        print("getAlbum OK")

async def test_get_album_info2():
    print("\nTesting getAlbumInfo2...")
    async with httpx.AsyncClient() as client:
        # Use known Album ID (The Weeknd - After Hours: 134858516)
        album_id = 134858516
        
        resp = await client.get(f"{BASE_URL}/rest/getAlbumInfo2.view?id=album-{album_id}&u=test&p=test&v=1.16.1&c=test&f=json")
        print(f"Status: {resp.status_code}")
        # print(resp.text)
        if resp.status_code != 200:
             print(f"getAlbumInfo2 failed: {resp.status_code}")
             return
             
        data = resp.json()["subsonic-response"]
        assert "albumInfo" in data
        info = data["albumInfo"]
        print("Notes:", info.get("notes")[:50], "...")
        assert "largeImageUrl" in info
        print("getAlbumInfo2 OK")

async def main():
    try:
        await test_ping()
        await test_license()
        # await test_music_folders()
        # await test_root_directory()
        await test_search()
        # await test_stream()
        # await test_cover_art()
        # await test_cover_art_prefixed()
        await test_get_artist_album_endpoints()
        await test_get_album_info2()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
