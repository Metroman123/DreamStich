from pathlib import Path
import random
import yt_dlp


KEYWORD_BANK = {
    "liminal_empty_spaces": [
        "liminal space", "empty mall", "abandoned food court",
        "empty office building", "vacant hotel hallway",
        "airport at night", "empty school corridor",
        "parking garage ambience", "dead mall walkthrough",
        "empty hospital hallway", "empty convention center",
        "closed department store", "abandoned kmart",
        "empty motel hallway", "empty subway station",
        "empty train platform at night", "vacant office cubicles",
        "empty college campus", "abandoned shopping plaza",
    ],

    "surreal_dreamlike": [
        "dreamcore", "weirdcore", "surreal video", "uncanny footage",
        "strange nostalgia", "found footage aesthetic",
        "impossible architecture", "backrooms footage",
        "dreamlike short film", "surreal liminal footage",
        "uncanny valley video", "strange dream footage",
        "experimental dream film", "dream logic animation",
        "liminal dream sequence", "surreal walking video",
    ],

    "vaporwave_nostalgia": [
        "vaporwave visuals", "mallsoft ambience", "1990s commercial",
        "2000s infomercial", "windows 95 aesthetic", "CRT television footage",
        "retro computer graphics", "vaporwave mall footage",
        "retro anime city pop visuals", "old weather channel music",
        "90s shopping mall footage", "80s mall commercial",
        "early 2000s internet aesthetic", "y2k computer graphics",
    ],

    "eerie_atmospheric": [
        "foggy street at night", "night drive ambience",
        "abandoned amusement park", "dark ambient footage",
        "empty city at night", "rainy parking lot", "eerie hallway",
        "creepy VHS footage", "analog horror ambience",
        "stormy night camcorder", "empty road at night",
        "lonely gas station at night", "dark stairwell footage",
        "abandoned hotel night", "security camera eerie footage",
    ],

    "youtube_poop_absurdism": [
        "youtube poop", "YTP", "surreal meme edit", "random internet humor",
        "chaotic video edit", "sentence mixing", "weird video remix",
        "old youtube meme", "windows movie maker meme",
        "internet nonsense video", "absurd video edit",
        "deep fried meme video", "2007 youtube poop",
    ],

    "smooth_jazz_lounge": [
        "Lindsey Webster live", "smooth jazz live", "jazz lounge",
        "late night jazz club", "contemporary jazz", "saxophone performance",
        "Sade live concert", "Sade smooth operator live",
        "city lights jazz ambience", "late night saxophone",
        "quiet storm radio", "smooth jazz night drive",
        "jazz fusion live", "neo soul live performance",
    ],

    "music_random": [
        "city pop live", "Japanese city pop visuals",
        "80s synthpop music video", "new jack swing video",
        "lofi hip hop rain window", "vapor soul music video",
        "old r&b music video", "quiet storm visuals",
        "trip hop music video", "downtempo visualizer",
        "ambient electronic visuals", "experimental music video",
    ],

    "corporate_vhs": [
        "corporate training VHS", "workplace safety video",
        "orientation video", "sales seminar recording",
        "employee training video", "old corporate video",
        "customer service training tape", "1990s corporate training",
        "retail training video VHS", "business etiquette video",
        "office training film", "old sales training tape",
    ],

    "old_educational": [
        "old educational film", "science classroom VHS",
        "1990s school video", "instructional tape",
        "educational filmstrip", "old classroom video",
        "80s educational video", "health class VHS",
        "school safety video", "old math lesson video",
        "public school documentary", "library instructional video",
    ],

    "public_access_weirdness": [
        "public access television", "local access television",
        "small town cable show", "community TV recording",
        "public access oddity", "weird TV broadcast",
        "old television recording", "local news 1990s",
        "public access call in show", "community bulletin channel",
        "local commercial compilation", "small town news broadcast",
    ],

    "strange_technology": [
        "old computer demonstration", "windows 98 showcase",
        "retro tech demo", "old computer commercial",
        "consumer electronics expo 1990s", "internet cafe footage",
        "old software tutorial", "windows xp tutorial",
        "macintosh demo 1980s", "computer chronicles episode",
        "old internet documentary", "retro computer lab footage",
    ],

    "ps1_ps2_game_ambience": [
        "ps1 graphics ambience", "ps2 startup ambience",
        "playstation 2 menu ambience", "low poly 3d environment",
        "early 2000s video game graphics", "dreamcast menu ambience",
        "n64 empty level ambience", "source engine empty map",
        "garrys mod empty map ambience", "half life empty map",
        "old 3d game test footage", "retro game menu loop",
    ],

    "nature_dream_imagery": [
        "forest at dusk", "ocean waves at night", "snowfall ambience",
        "desert sunset", "foggy forest", "lonely beach at night",
        "misty mountain", "rainy forest walk",
        "windy field at night", "abandoned building nature reclaiming",
        "overgrown house footage", "quiet lake at night",
    ],

    "cozy_human_spaces": [
        "coffee shop ambience", "bookstore walkthrough",
        "aquarium footage", "quiet train ride",
        "late night diner", "rainy window ambience",
        "hotel lobby ambience", "laundromat ambience",
        "airport lounge ambience", "library at night ambience",
        "empty restaurant after closing", "quiet apartment night ambience",
    ],

    "weather_and_warning": [
        "weather channel 1990s", "local forecast VHS",
        "EAS alert test", "severe weather warning",
        "tornado siren footage", "green sky storm footage",
        "thunderstorm night camcorder", "hurricane news footage",
        "old weather radar loop", "emergency broadcast test",
    ],

    "internet_archeology_weird": [
        "early youtube video 2006", "windows movie maker 2007 masterpiece",
        "unregistered hypercam 2 tutorial", "weird flash game footage",
        "old flash animation", "geocities aesthetic video",
        "old web series reupload", "internet cafe 2000s",
        "old 3d chatroom footage", "second life weird footage",
        "habbo hotel old footage", "myspace era video",
    ],

    "unsettling_simulations": [
        "gmod arg footage", "garrys mod empty map ambience",
        "source engine eerie silence", "creepy cgi character 2000s",
        "old blender animation test", "uncanny valley animation",
        "cgi test footage 1990s", "strange simulation video",
        "ai generated uncanny video", "virtual world empty footage",
    ],

    "random_everyday_life": [
        "small town parade VHS", "county fair footage",
        "local talent show", "home video 1990s",
        "family camcorder footage", "church picnic recording",
        "old birthday party VHS", "school play recording",
        "mall Santa VHS", "old wedding reception video",
        "community event footage", "local festival camcorder",
    ],

    "transportation": [
        "train ride at night", "empty train station",
        "airport terminal night", "bus ride rainy night",
        "subway ride ambience", "ferry ride foggy",
        "highway night drive", "dashcam rain night",
        "old airport footage 1990s", "airplane cabin ambience",
    ],

    "retail_and_service_spaces": [
        "grocery store ambience", "old supermarket commercial",
        "empty walmart at night", "closed mall footage",
        "retail store training video", "fast food training VHS",
        "old mcdonalds training video", "pizza hut commercial 1990s",
        "blockbuster video store footage", "radio shack commercial",
        "toys r us commercial 1990s", "sears commercial 1990s",
    ],

    "paranormal_found_footage": [
        "ghost hunting VHS", "paranormal investigation footage",
        "EVP recording session", "abandoned asylum night vision",
        "haunted house camcorder", "security camera ghost footage",
        "cryptid found footage", "strange lights in sky VHS",
        "ufo sighting camcorder", "analog horror found footage",
    ],

    "abstract_visuals": [
        "glitch art video", "datamosh video", "video synthesis",
        "analog video feedback", "CRT glitch visuals",
        "abstract animation", "experimental short film",
        "psychedelic visualizer", "fractal animation",
        "old computer animation festival",
    ],
}


def run_crawler(
    videos_dir="Videos",
    videos_per_keyword=2,
    max_total_downloads=500,
    status_callback=None,
):
    videos_dir = Path(videos_dir)
    videos_dir.mkdir(exist_ok=True)

    def status(text):
        print(text)
        if status_callback:
            status_callback(text)

    search_jobs = []
    for category, keywords in KEYWORD_BANK.items():
        for keyword in keywords:
            search_jobs.append((category, keyword))

    random.shuffle(search_jobs)

    ydl_opts = {
        "outtmpl": str(videos_dir / "%(title).80s [%(id)s].%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "ignoreerrors": True,
        "noplaylist": True,
        "writedescription": True,
        "writeinfojson": True,
        "download_archive": str(videos_dir / "downloaded.txt"),
        "quiet": True,
    }

    download_count = len(list(videos_dir.glob("*.mp4")))
    status(f"Crawl started. Current vault count: {download_count}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for category, keyword in search_jobs:
            if download_count >= max_total_downloads:
                status(f"Target download limit reached: {download_count}/{max_total_downloads}.")
                break

            query = f"ytsearch{videos_per_keyword}:{keyword}"

            status(f"Searching [{category}]: {keyword}")

            try:
                ydl.download([query])
            except Exception as e:
                status(f"Skipped due to error: {e}")

            download_count = len(list(videos_dir.glob("*.mp4")))
            status(f"Vault status: {download_count}/{max_total_downloads}")

    status(f"Crawl complete. Final count: {download_count}")
    return download_count