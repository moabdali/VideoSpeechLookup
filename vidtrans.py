import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="whisper") # suppress Whisper message
warnings.filterwarnings("ignore", category=UserWarning,   module="whisper")
import whisper
import os
from datetime import timedelta
import ffmpeg
import re
from PIL import Image, ImageDraw, ImageFont
import webbrowser


# Explicitly set the path to ffmpeg if it's installed in a specific location
os.environ["FFMPEG_BINARY"] = "C:\\ffmpeg\\bin\\ffmpeg.exe"  # Update this path if needed
folder_path = "C:\\videostuff"  # Update this path as needed
screenshot_folder = os.path.join(folder_path, "screenshots")  # Path for screenshots
os.makedirs(screenshot_folder, exist_ok=True)


# Load Whisper model; Whisper is the transcriber that generates subs for us
model = whisper.load_model("base") # base is the default; you can use: tiny, base, small, medium, and large
number_of_results = 0


# Creates subtitles for a specific video
def transcribe_video(video_path):
    """Transcribe the audio of a video file with progress estimation."""
    print(f"Starting transcription for: {video_path}")
    print("Note that this process takes a long time...")
    result = model.transcribe(video_path, word_timestamps=True)
    
    '''
    segments = result['segments']

    num_of_segments = len(result['segments'])
    
    for i, segment in enumerate(segments):
        progress = (i / num_of_segments) * 100
        print(f"Progress: {progress:.2f}% - Current timestamp: {timedelta(seconds=segment['end'])}")
    '''
    print(f"Completed transcription for: {video_path}")
    return result


# save the resulting transcript in different file formats
def save_transcripts(transcript, video_path):
    """Save transcript in TXT, SRT, and VTT formats."""
    base_filename = os.path.splitext(video_path)[0]

    # Save as TXT (useful for simply reading the subs using a text editor)
    with open(f"{base_filename}.txt", "w") as txt_file:
        txt_file.write(transcript['text'])

    # Save as SRT (the program will use this one)
    with open(f"{base_filename}.srt", "w") as srt_file:
        for i, segment in enumerate(transcript['segments']):
            start_time = timedelta(seconds=segment['start'])
            end_time = timedelta(seconds=segment['end'])
            srt_file.write(f"{i + 1}\n")
            srt_file.write(f"{str(start_time)[:-3]} --> {str(end_time)[:-3]}\n")
            srt_file.write(f"{segment['text']}\n\n")
    
    # Save as VTT (the option was readily available, so no harm in including it)
    with open(f"{base_filename}.vtt", "w") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for segment in transcript['segments']:
            start_time = timedelta(seconds=segment['start'])
            end_time = timedelta(seconds=segment['end'])
            vtt_file.write(f"{str(start_time)[:-3].replace('.', ',')} --> {str(end_time)[:-3].replace('.', ',')}\n")
            vtt_file.write(f"{segment['text']}\n\n")


# parse the srt file and group lines together as needed 
def parse_srt_file(srt_path):
    """Parse an SRT file and return a list of segments with start times and text."""
    segments = []
    with open(srt_path, "r", encoding="utf-8") as srt_file:
        srt_content = srt_file.read()

    # combine multiple lines as an individual subtitle group
    pattern = re.compile(
        r"(\d+)\n(\d+:\d+:\d+\.\d+) --> (\d+:\d+:\d+\.\d+)\n(.+?)(?=\n\n|\Z)",
        re.DOTALL
    )
    
    matches = pattern.findall(srt_content)

    for match in matches:
        index, start_time, end_time, text = match
        start_time_obj = convert_to_timedelta(start_time)
        end_time_obj = convert_to_timedelta(end_time)
        text = " ".join(line.strip() for line in text.splitlines())
        segments.append({'start': start_time_obj, 'end': end_time_obj, 'text': text})

    return segments


# get a usable timedelta
def convert_to_timedelta(timestamp):
    """Convert timestamp of format H:MM:SS.mmm to timedelta."""
    hours, minutes, seconds_milliseconds = timestamp.split(":")
    seconds, milliseconds = seconds_milliseconds.split(".")
    return timedelta(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds)
    )


# transcribe all videos in the folder
def transcribe_videos_in_folder(folder_path):
    """Transcribe all videos in a folder and save transcripts to text, SRT, and VTT files."""
    transcripts = {}
    
    for filename in os.listdir(folder_path):
        if filename.endswith(('.mp4', '.mkv', '.avi', '.mov')):
            video_path = os.path.join(folder_path, filename)
            print("Video Path:", video_path)
            print(f"Transcribing {filename}...")

            result = transcribe_video(video_path)
            transcripts[filename] = result
            save_transcripts(result, video_path)
            print(f"Transcripts saved for {filename}")

    return transcripts


# find all instances that match your search phrase and make screenshots with the captions
def search_in_transcripts(transcripts, folder_path, search_term):
    """
    Search transcripts for a term, returning results with timestamps, optional screenshots,
    and context from the subtitle before and after the match.
    """
    results = {}
    all_timestamps = []  # Collect timestamps and matched text for HTML
    global number_of_results
    number_of_results = 0
    number_of_this_video = 0

    # find the word in question; coded to ignore results where the word is inside another word (for example,
    # if looking for "here", it will NOT return results for "tHEREfore".  However, it will find instances of
    # "here!" and "here." and so on. Open to change based on users' requests.
    search_pattern = re.compile(rf"\b{re.escape(search_term)}\b[.,!?]*", re.IGNORECASE)
    
    for video_name in transcripts.keys():
        print(f"Searching in {video_name}...")
        matches = []

        base_name = os.path.splitext(video_name)[0]
        video_path = None
        for ext in ['.mp4', '.mkv', '.avi', '.mov']:
            potential_video_path = os.path.join(folder_path, base_name + ext)
            if os.path.exists(potential_video_path):
                video_path = potential_video_path
                break
        
        if video_path is None:
            print(f"No video file found for {video_name}. Skipping screenshot capture.")
            continue

        srt_path = os.path.join(folder_path, f"{base_name}.srt")
        if os.path.exists(srt_path):
            segments = parse_srt_file(srt_path)
            for i, segment in enumerate(segments):
                if search_pattern.search(segment['text']):
                    # Gather context: previous and next segments if they exist
                    prev_segment = segments[i - 1] if i > 0 else None
                    next_segment = segments[i + 1] if i < len(segments) - 1 else None

                    # Format the context
                    context_text = ""
                    if prev_segment:
                        context_text += f"[Before] {str(prev_segment['start'])}: {prev_segment['text']}\n"
                    context_text += f"[Match] {str(segment['start'])}: {segment['text']}\n"
                    if next_segment:
                        context_text += f"[After] {str(next_segment['start'])}: {next_segment['text']}"

                    # Format timestamp using format_timestamp function
                    timestamp_str = format_timestamp(segment['start'].total_seconds())

                    # Append the formatted context to the HTML output list
                    all_timestamps.append((video_name, timestamp_str, context_text))

                    # Take screenshot with formatted timestamp
                    matches.append((segment['start'], context_text))
                    take_screenshot(video_path, segment['start'].total_seconds(), segment['text'], search_term)
                    number_of_results += 1
                    number_of_this_video += 1
        if matches:
            results[video_name] = matches
        print("Results in this video: ", number_of_this_video)
        number_of_this_video = 0
        
    print("*" * 20)
    print("Found", number_of_results, "total result(s).")
    print("*" * 20, "\n")
    # Ask if user wants to save an HTML file for all results
    if number_of_results > 0:
        user_choice = input("Do you want to create and view some HTML with the data? [Will be saved in Screenshots] (y/n): ")
        if user_choice.lower() == 'y':
            generate_html(all_timestamps, search_term)
    number_of_results = 0
    return results



def generate_html(timestamps, search_term):
    """Generate an HTML file in the screenshots folder, with context and screenshot toggles."""
    html_path = os.path.join(screenshot_folder, "search_results.html")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Search Results</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                color: #333;
                background-color: #f4f4f4;
                line-height: 1.6;
            }}
            h1 {{
                color: #00509E;
                border-bottom: 2px solid #ddd;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            .result {{
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 15px;
                box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.1);
            }}
            .context-before, .context-after {{
                display: inline;  /* Show context by default */
                color: #555;
            }}
            .screenshot {{
                display: inline; /* Ensure screenshots are visible on load */
                margin-top: 10px;
                max-width: 100%;
                border-radius: 5px;
                border: 1px solid #ddd;
            }}
            .toggle-button, .global-toggle-button {{
                color: #00509E;
                cursor: pointer;
                text-decoration: underline;
                font-size: 0.9em;
                margin-right: 15px;
            }}
            .toggle-button:hover, .global-toggle-button:hover {{
                text-decoration: none;
                background-color: #e0f1ff;
                padding: 3px;
                border-radius: 3px;
            }}
            .highlight {{
                background-color: yellow;
                font-weight: bold;
            }}
            .timestamp {{
                font-weight: bold;
                color: #00509E;
                margin-top: 5px;
            }}
        </style>
        <script>
            function toggleContext() {{
                var contextsBefore = document.querySelectorAll('.context-before');
                var contextsAfter = document.querySelectorAll('.context-after');
                var isCurrentlyShown = contextsBefore[0].style.display === "inline";
                contextsBefore.forEach(context => {{
                    context.style.display = isCurrentlyShown ? "none" : "inline";
                }});
                contextsAfter.forEach(context => {{
                    context.style.display = isCurrentlyShown ? "none" : "inline";
                }});
            }}

            function toggleAllScreenshots() {{
                var screenshots = document.querySelectorAll('.screenshot');
                var isCurrentlyShown = screenshots[0].style.display === "inline";
                screenshots.forEach(screenshot => {{
                    screenshot.style.display = isCurrentlyShown ? "none" : "inline";
                }});
            }}

            window.onload = function() {{
                var contextsBefore = document.querySelectorAll('.context-before');
                var contextsAfter = document.querySelectorAll('.context-after');
                contextsBefore.forEach(context => context.style.display = "inline");
                contextsAfter.forEach(context => context.style.display = "inline");

                var screenshots = document.querySelectorAll('.screenshot');
                screenshots.forEach(screenshot => screenshot.style.display = "inline");
            }};
        </script>
    </head>
    <body>
        <h1>Search Results</h1>
        <button class="global-toggle-button" onclick="toggleContext()">Show/Hide All Context</button>
        <button class="global-toggle-button" onclick="toggleAllScreenshots()">Show/Hide All Screenshots</button>
        <ul>
    """

    for index, (video_name, timestamp, context_text) in enumerate(timestamps):
        time_parts = timestamp.split('.')
        timestamp = time_parts[0]
        screenshot_filename = f"{os.path.splitext(video_name)[0]}_screenshot_{timestamp.replace(':', '-')}.png"
        
        # Highlight the match term in the match text
        highlighted_context_text = context_text.replace(
            search_term,
            f"<span class='highlight'>{search_term}</span>"
        )

        # Structure HTML with only one line break after the match
        html_content += f"""
            <li class="result">
                <div class="timestamp"><strong>{video_name} - {timestamp}</strong></div>
                <div>
                    <span class="context-before"> {highlighted_context_text.split('[Match]')[0]}</span><br>
                    <span class="match">[Match] {highlighted_context_text.split('[Match]')[1].split('[After]')[0]}</span><br>
                    <span class="context-after">[After] {highlighted_context_text.split('[After]')[1]}</span><br>
                    <img src="{screenshot_filename}" alt="Screenshot for {timestamp}" class="screenshot">
                </div>
            </li>
        """
    
    html_content += """
        </ul>
    </body>
    </html>
    """

    with open(html_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    # Open the generated HTML in the default web browser
    webbrowser.open(f"file://{html_path}")
    print(f"HTML file with timestamps saved to {html_path}")


# open the video, grab the frame at the timestamp, overlay the caption, save a png of the result.
def take_screenshot(video_path, time, overlay_text, match_word):
    """Capture a screenshot from a video at a specific time with overlay text and save to screenshots folder."""
    # Format the timestamp with zero padding for filenames
    formatted_time = format_timestamp(time).replace(":", "-")
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(screenshot_folder, f"{video_name}_screenshot_{formatted_time}.png")

    try:
        adjusted_time = time + 0.1  # Small adjustment for frame sync
        temp_path = output_path.replace(".png", "_temp.png")

        # Capture screenshot using ffmpeg
        ffmpeg.input(video_path, ss=adjusted_time).output(temp_path, vframes=1).run(overwrite_output=True)
        print(f"Screenshot saved to {temp_path}")

        # Open screenshot for overlay processing
        image = Image.open(temp_path)
        draw = ImageDraw.Draw(image)

        # Set font and calculate text dimensions
        font_size = 20
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

        text_width, text_height = draw.textbbox((0, 0), overlay_text, font=font)[2:]
        while text_width > image.width - 20 and font_size > 10:
            font_size -= 1
            font = ImageFont.truetype("arial.ttf", font_size)
            text_width, text_height = draw.textbbox((0, 0), overlay_text, font=font)[2:]

        # Draw overlay with background
        text_position = (10, image.height - text_height - 20)
        background_position = (text_position[0] - 5, text_position[1] - 5,
                               text_position[0] + text_width + 5, text_position[1] + text_height + 5)
        draw.rectangle(background_position, fill=(0, 0, 0))
        
        # Highlight match word
        pattern = re.compile(rf"\b{re.escape(match_word)}\b[.,!?]*", re.IGNORECASE)
        parts = pattern.split(overlay_text)
        matches = pattern.findall(overlay_text)

        x_offset = text_position[0]
        for i, part in enumerate(parts):
            draw.text((x_offset, text_position[1]), part, font=font, fill=(255, 255, 255))
            x_offset += draw.textlength(part, font=font)
            if i < len(matches):
                draw.text((x_offset, text_position[1]), matches[i], font=font, fill=(255, 0, 0))
                x_offset += draw.textlength(matches[i], font=font)

        # Save final image and clean up
        image.save(output_path)
        print(f"Screenshot with overlay saved to {output_path}")
        image.close()
        os.remove(temp_path)

    except ffmpeg.Error as e:
        error_message = e.stderr.decode() if e.stderr else "No error message provided by ffmpeg."
        print("ffmpeg error:", error_message)


# format the timestamp to make it look better (prior to this, we had stuff like 3:5:34 instead of 3:05:34
def format_timestamp(seconds):
    """
    Convert seconds to HH:MM:SS format with zero-padding to ensure consistency.
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def transcribe_specific_videos(folder_path):
    """Allow user to select specific videos to transcribe."""
    video_files = [f for f in os.listdir(folder_path) if f.endswith(('.mp4', '.mkv', '.avi', '.mov'))]
    if not video_files:
        print("No videos found in the specified folder.")
        return

    print("\nSelect videos to transcribe by typing the number(s) one at a time. Leave blank to finish.")
    for i, filename in enumerate(video_files, 1):
        print(f"{i}. {filename}")

    selected_videos = []
    while True:
        choice = input("Enter video number (leave blank when done): ")
        if not choice:
            break
        try:
            index = int(choice) - 1
            if 0 <= index < len(video_files):
                selected_videos.append(video_files[index])
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or leave blank to finish.")

    for filename in selected_videos:
        video_path = os.path.join(folder_path, filename)
        transcript = transcribe_video(video_path)
        save_transcripts(transcript, video_path)



# main menu
def main():
    while True:
        print("Choose an action:\n1. Transcribe All Videos\n2. Transcribe Remaining Videos\n3. Transcribe Specific Video(s)\n4. Search Transcripts")
        action = input("Your choice: ")
        
        if action == "1":
            print("\nTranscribing all videos...")
            transcribe_all_videos(folder_path)
        elif action == "2":
            print("\nTranscribing remaining videos (those without existing transcripts)...")
            transcribe_remaining_videos(folder_path)
        elif action == "3":
            print("\nTranscribing specific videos...")
            transcribe_specific_videos(folder_path)
        elif action == "4":
            search_term = input("Enter search term: ")
            transcripts = {filename: None for filename in os.listdir(folder_path) if filename.endswith(".srt")}
            if transcripts:
                results = search_in_transcripts(transcripts, folder_path, search_term)
                if results:
                    print("***********************************")
                    print("SEARCH RESULTS:")
                    print("***********************************")
                    for video, matches in results.items():
                        print(f"\nIn {video}:")
                        for timestamp, text in matches:
                            print(f"{text}")
                            print("-"*10)
                    
                else:
                    print("No matches found.")
            else:
                print("No transcripts found. Run the transcription first.")
        else:
            print("Invalid action. Please choose 1, 2, 3, or 4.")

if __name__ == "__main__":
    main()
