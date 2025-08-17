import io
import os
import random
import asyncio
import logging
import tempfile
import subprocess
import requests
import re
import math
import colorsys
import gc
import psutil
import edge_tts
import json
import urllib.parse
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips, concatenate_audioclips
import numpy as np

logging.basicConfig(level=logging.INFO)

def get_memory_usage():
    """Get current memory usage in MB"""
    try:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        return memory_mb
    except:
        return 0

def force_memory_cleanup():
    """Force garbage collection and memory cleanup"""
    try:
        gc.collect()
        # Force Python to release memory back to OS (Linux)
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except:
            pass  # Not on Linux or library not available
    except:
        pass
    finally:
        gc.collect()  # Always do garbage collection

def create_video_streaming_ffmpeg(frame_data_list, output_path, audio_bitrate=96, video_bitrate=None, fps=24):
    """
    MEMORY-EFFICIENT: Create video by streaming frames directly to FFmpeg
    instead of loading all clips into memory with MoviePy.
    
    Args:
        frame_data_list: List of (image_path, audio_path, duration) tuples
        output_path: Where to save the final video
        audio_bitrate: Audio bitrate in kbps
        video_bitrate: Video bitrate in kbps  
        fps: Frames per second
    """
    import subprocess
    import tempfile
    import os
    
    print(f"[FFMPEG] 🌊 Starting streaming video creation with {len(frame_data_list)} frames")
    memory_before = get_memory_usage()
    print(f"[MEMORY] 💾 Memory before FFmpeg streaming: {memory_before:.1f}MB")
    
    # ULTRA MEMORY EFFICIENT: Create temporary files list for FFmpeg concat demuxer
    # Use smaller batches for 512MB limit
    max_segments_in_memory = 5  # Keep only 5 segments at once for 512MB limit
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as concat_file:
        concat_list_path = concat_file.name
        created_segments = []  # Track created segments for cleanup
        
        for i, (image_path, audio_path, duration) in enumerate(frame_data_list):
            # Create temporary video segment for this frame
            temp_segment = os.path.join(os.path.dirname(output_path), f"temp_segment_{i:03d}.mp4")
            
            # MEMORY OPTIMIZATION: Process one frame at a time
            try:
                if audio_path and os.path.exists(audio_path):
                    # Frame with audio
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1', '-i', image_path,  # Loop image
                        '-i', audio_path,  # Audio input
                        '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', f'{audio_bitrate}k'
                    ]
                    
                    # Add CRF or bitrate based on parameter
                    if video_bitrate is None:
                        cmd.extend(['-crf', '23'])
                    else:
                        cmd.extend(['-b:v', f'{video_bitrate}k'])
                    
                    # Add remaining parameters
                    cmd.extend([
                        '-r', str(fps),
                        '-t', str(duration),  # Explicit duration to match audio
                        '-movflags', '+faststart',
                        temp_segment
                    ])
                else:
                    # Frame without audio (create silent video)
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1', '-i', image_path,
                        '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                        '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', f'{audio_bitrate}k'
                    ]
                    
                    # Add CRF or bitrate based on parameter
                    if video_bitrate is None:
                        cmd.extend(['-crf', '23'])
                    else:
                        cmd.extend(['-b:v', f'{video_bitrate}k'])
                    
                    # Add remaining parameters
                    cmd.extend([
                        '-r', str(fps),
                        '-t', str(duration),  # Duration for silent video
                        '-movflags', '+faststart',
                        temp_segment
                    ])
                
                # Run FFmpeg for this segment
                subprocess.run(cmd, capture_output=True, check=True)
                
                # Add to concat list
                concat_file.write(f"file '{temp_segment}'\n")
                created_segments.append(temp_segment)
                
                # ULTRA MEMORY OPTIMIZATION: Clean up old segments to keep memory low
                if len(created_segments) > max_segments_in_memory:
                    # Keep only the most recent segments in temp folder
                    old_segment = created_segments.pop(0)
                    # Don't delete yet - needed for final concatenation
                
                # Memory check every 2 frames (more frequent for 512MB limit)
                if (i + 1) % 2 == 0:
                    current_memory = get_memory_usage()
                    print(f"[MEMORY] 💾 Memory after segment {i+1}: {current_memory:.1f}MB")
                    if current_memory > 350:  # 68% of 512MB (more conservative)
                        print(f"[MEMORY] ⚠️ HIGH MEMORY during streaming: {current_memory:.1f}MB")
                        force_memory_cleanup()
                
            except subprocess.CalledProcessError as e:
                print(f"[FFMPEG] ❌ Error creating segment {i}: {e}")
                # Create a fallback silent segment
                fallback_cmd = [
                    'ffmpeg', '-y',
                    '-f', 'lavfi', '-i', f'color=black:size=1280x720:duration={duration}',
                    '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                    '-c:v', 'libx264', '-preset', 'ultrafast',
                    '-c:a', 'aac', '-b:a', f'{audio_bitrate}k'
                ]
                
                # Add CRF or bitrate based on parameter
                if video_bitrate is None:
                    fallback_cmd.extend(['-crf', '23'])
                else:
                    fallback_cmd.extend(['-b:v', f'{video_bitrate}k'])
                
                # Add remaining parameters
                fallback_cmd.extend([
                    '-r', str(fps),
                    temp_segment
                ])
                subprocess.run(fallback_cmd, capture_output=True)
                concat_file.write(f"file '{temp_segment}'\n")
    
    # Now concatenate all segments using FFmpeg concat demuxer
    print("[FFMPEG] 🔗 Concatenating segments with FFmpeg...")
    
    # Step 1: Concatenate video segments (without background music)
    temp_concat_path = output_path.replace('.mp4', '_temp_concat.mp4')
    concat_cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0', '-i', concat_list_path,
        '-c', 'copy',  # Copy streams without re-encoding
        '-movflags', '+faststart',
        temp_concat_path
    ]
    
    try:
        subprocess.run(concat_cmd, capture_output=True, check=True)
        print("[FFMPEG] ✅ Video segments concatenated")
        
        # Step 2: Add background music with proper volume mixing
        sound_effect_path = os.path.join(os.path.dirname(__file__), "assets", "sound_effect.mp3")
        if os.path.exists(sound_effect_path):
            print("[FFMPEG] 🎵 Adding background music...")
            music_cmd = [
                'ffmpeg', '-y',
                '-i', temp_concat_path,  # Main video with TTS
                '-i', sound_effect_path,  # Background music
                '-filter_complex', '[0:a]volume=1.0[main];[1:a]volume=0.15,aloop=loop=-1:size=2e+09[bg];[main][bg]amix=inputs=2:duration=first:dropout_transition=2',
                '-c:v', 'copy',  # Don't re-encode video
                '-c:a', 'aac',
                '-movflags', '+faststart',
                output_path
            ]
            subprocess.run(music_cmd, capture_output=True, check=True)
            print("[FFMPEG] ✅ Background music added (TTS:100%, BG:15%)")
            
            # Clean up temp file
            try:
                os.remove(temp_concat_path)
            except:
                pass
        else:
            # No background music available, just move the temp file
            import shutil
            shutil.move(temp_concat_path, output_path)
            print("[FFMPEG] ✅ Video complete (no background music found)")
            
        print("[FFMPEG] ✅ Streaming video creation complete")
        
        # Cleanup temporary files (use created_segments list for more reliable cleanup)
        for temp_segment in created_segments:
            try:
                os.remove(temp_segment)
            except:
                pass
        try:
            os.remove(concat_list_path)
        except:
            pass
        
        memory_after = get_memory_usage()
        print(f"[MEMORY] 💾 Memory after FFmpeg streaming: {memory_after:.1f}MB")
        
    except subprocess.CalledProcessError as e:
        print(f"[FFMPEG] ❌ Error concatenating segments: {e}")
        raise

# Voice assignment system for users
user_voice_assignments = {}

def get_edge_tts_voices():
    """Return list of verified Edge TTS voices for Edge TTS 7.2.0"""
    return [
        "en-US-AriaNeural",         # Female
        "en-US-JennyNeural",        # Female  
        "en-US-GuyNeural",          # Male
        "en-US-ChristopherNeural",  # Male
        "en-US-AndrewNeural",       # Male
        "en-US-EmmaNeural",         # Female
        "en-US-BrianNeural",        # Male
        "en-US-AvaNeural",          # Female
        "en-US-EricNeural",         # Male
        "en-US-MichelleNeural",     # Female
        "en-US-RogerNeural",        # Male
        "en-US-SteffanNeural"       # Male
    ]

def assign_voice_to_user(user_id):
    """Assign a random Edge TTS voice to a user (persistent for video session)"""
    if user_id not in user_voice_assignments:
        voices = get_edge_tts_voices()
        user_voice_assignments[user_id] = random.choice(voices)
        print(f"[VOICE] Assigned voice {user_voice_assignments[user_id]} to user {user_id}")
    return user_voice_assignments[user_id]

def extract_media_links(text):
    """Extract media links from text and return link info"""
    media_links = []
    
    # YouTube links
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in youtube_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            video_id = match.group(1)
            media_links.append({
                'type': 'youtube',
                'url': match.group(0),
                'video_id': video_id,
                'thumbnail_url': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                'title': f'YouTube Video'
            })
    
    # Twitter/X links
    twitter_pattern = r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/(\d+)'
    matches = re.finditer(twitter_pattern, text)
    for match in matches:
        tweet_id = match.group(1)
        media_links.append({
            'type': 'twitter',
            'url': match.group(0),
            'tweet_id': tweet_id,
            'thumbnail_url': None,  # We'll try to get this from API or use placeholder
            'title': 'Twitter Post'
        })
    
    # Instagram links
    instagram_pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)'
    matches = re.finditer(instagram_pattern, text)
    for match in matches:
        post_id = match.group(1)
        media_links.append({
            'type': 'instagram',
            'url': match.group(0),
            'post_id': post_id,
            'thumbnail_url': None,
            'title': 'Instagram Post'
        })
    
    # TikTok links
    tiktok_pattern = r'(?:https?://)?(?:www\.)?tiktok\.com/@[\w.]+/video/(\d+)'
    matches = re.finditer(tiktok_pattern, text)
    for match in matches:
        video_id = match.group(1)
        media_links.append({
            'type': 'tiktok',
            'url': match.group(0),
            'video_id': video_id,
            'thumbnail_url': None,
            'title': 'TikTok Video'
        })
    
    # Generic image links
    image_pattern = r'(https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s]*)?)'
    matches = re.finditer(image_pattern, text, re.IGNORECASE)
    for match in matches:
        url = match.group(1)
        media_links.append({
            'type': 'image',
            'url': url,
            'thumbnail_url': url,
            'title': 'Image'
        })
    
    return media_links

def clean_text_for_speech(text):
    """Clean text to keep only speakable content, but preserve media link context"""
    # Check if message is emoji-only FIRST
    if is_emoji_only(text):
        # For emoji-only messages, keep them for TTS 
        return text.strip()
    
    # First extract media links for context
    media_links = extract_media_links(text)
    
    # Replace media links with descriptive text for TTS
    for link in media_links:
        if link['type'] == 'youtube':
            text = text.replace(link['url'], f"shared a YouTube video")
        elif link['type'] == 'twitter':
            text = text.replace(link['url'], f"shared a Twitter post")
        elif link['type'] == 'instagram':
            text = text.replace(link['url'], f"shared an Instagram post")
        elif link['type'] == 'tiktok':
            text = text.replace(link['url'], f"shared a TikTok video")
        elif link['type'] == 'image':
            text = text.replace(link['url'], f"shared an image")
    
    # Remove remaining URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Remove Discord invite links
    text = re.sub(r'discord\.gg/[a-zA-Z0-9]+', '', text)
    
    # Remove file attachments mentions
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)  # Markdown links
    
    # REMOVE MARKDOWN FORMATTING for TTS (so it doesn't read symbols)
    # Bold formatting **text** or __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    
    # Italic formatting *text* or _text_
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Strikethrough ~~text~~
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    
    # Code blocks ```text``` and `text`
    text = re.sub(r'```(.*?)```', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'\1', text)
    
    # Spoiler ||text||
    text = re.sub(r'\|\|(.*?)\|\|', r'\1', text)
    
    # Quotes > text
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    
    # Remove excessive punctuation that might confuse TTS
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    text = re.sub(r'[.]{3,}', '...', text)
    
    # Remove Discord custom emojis for TTS (but preserve Unicode emojis)
    text = re.sub(r'<:[^:]+:[0-9]+>', '', text)  # Discord custom emojis
    text = re.sub(r'<a:[^:]+:[0-9]+>', '', text)  # Discord animated emojis
    
    # REMOVE UNICODE EMOJIS from mixed text for TTS (emoji names confuse TTS)
    # Only keep emojis if the message was emoji-only (handled above)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U00002600-\U000027BF"  # miscellaneous symbols
        "\U000024C2-\U0001F251" 
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(' ', text)  # Replace with space to avoid word merging
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # If text is too short or just symbols, return empty
    if len(text.strip()) < 3 and not media_links and not re.search(r'[a-zA-Z]', text):
        return ""
    
    # If no meaningful text but has media, create descriptive text
    if len(text.strip()) < 3 and media_links:
        text = f"shared {len(media_links)} media item{'s' if len(media_links) > 1 else ''}"
    
    # INCREASED character limit for TTS (Edge TTS can handle longer text)
    if len(text) > 500:  # Increased from 200 to 500
        # Smart truncation at sentence boundary
        sentences = text.split('. ')
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence + ". ") <= 497:
                truncated += sentence + ". "
            else:
                break
        if truncated:
            text = truncated.rstrip(". ") + "..."
        else:
            text = text[:497] + "..."
    
    return text

def clean_text_for_display(text):
    """Clean text for display - preserve emojis but remove Discord formatting"""
    # Keep Unicode emojis but remove Discord custom emoji syntax
    text = re.sub(r'<:[^:]+:[0-9]+>', '', text)  # Discord custom emojis
    text = re.sub(r'<a:[^:]+:[0-9]+>', '', text)  # Discord animated emojis
    
    # Remove markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)  # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)  # Code
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def is_emoji_only(text):
    """Check if text contains only emojis and whitespace"""
    import re
    # Remove whitespace
    text_no_spaces = re.sub(r'\s+', '', text)
    
    # If empty after removing spaces, not emoji-only
    if not text_no_spaces:
        return False
    
    # Check if all remaining characters are emojis
    # Unicode emoji ranges (simplified)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U00002600-\U000027BF"  # miscellaneous symbols
        "\U000024C2-\U0001F251" 
        "]+", flags=re.UNICODE)
    
    # Remove all emojis and see if anything is left
    text_no_emojis = emoji_pattern.sub('', text_no_spaces)
    
    # If nothing left after removing emojis, it was emoji-only
    return len(text_no_emojis) == 0

async def download_thumbnail(url, temp_dir, max_size=(600, 400)):
    """Download and resize thumbnail from URL with video support"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Check if it's a video file by URL extension or content type
        content_type = response.headers.get('content-type', '').lower()
        is_video = (content_type.startswith('video/') or 
                   url.lower().endswith(('.mp4', '.webm', '.mov', '.avi', '.mkv', '.gif')))
        
        if is_video:
            # For videos, try to extract a frame from the middle
            try:
                # Save video to temp file for ffmpeg processing
                video_filename = f"temp_video_{hash(url) % 10000}.mp4"
                video_path = os.path.join(temp_dir, video_filename)
                
                with open(video_path, 'wb') as f:
                    f.write(response.content)
                
                # Use ffmpeg to extract a frame from 25% into the video
                frame_filename = f"frame_{hash(url) % 10000}.jpg"
                frame_path = os.path.join(temp_dir, frame_filename)
                
                # Extract frame at 2 seconds to avoid black intro frames
                ffmpeg_cmd = [
                    'ffmpeg', '-i', video_path, 
                    '-ss', '2',  # Seek to 2 seconds into video
                    '-vframes', '1',  # Extract 1 frame
                    '-y',  # Overwrite output
                    '-loglevel', 'quiet',  # Suppress ffmpeg output
                    frame_path
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=15)
                
                if result.returncode == 0 and os.path.exists(frame_path):
                    # Successfully extracted frame
                    img = Image.open(frame_path).convert('RGB')
                    img.thumbnail(max_size, Image.LANCZOS)
                    print(f"[THUMBNAIL] ✅ Extracted video frame from {url}")
                else:
                    raise Exception("FFmpeg frame extraction failed")
                    
            except Exception as ffmpeg_error:
                print(f"[THUMBNAIL] FFmpeg failed ({ffmpeg_error}), creating video placeholder")
                # Fallback to enhanced video placeholder
                img = Image.new('RGB', max_size, (20, 20, 40))
                draw = ImageDraw.Draw(img)
                
                # Create gradient background
                for y in range(max_size[1]):
                    ratio = y / max_size[1]
                    r = int(20 + ratio * 40)
                    g = int(20 + ratio * 30)
                    b = int(40 + ratio * 60)
                    draw.line([(0, y), (max_size[0], y)], fill=(r, g, b))
                
                # Add play button icon with glow
                center_x, center_y = max_size[0] // 2, max_size[1] // 2
                play_size = 80
                
                # Glow effect for play button
                for glow in range(8, 0, -1):
                    alpha = 255 - glow * 30
                    glow_color = (255, 255, 255, alpha) if glow < 4 else (100, 150, 255, alpha)
                    triangle_points = [
                        (center_x - play_size//2 - glow, center_y - play_size//2 - glow),
                        (center_x - play_size//2 - glow, center_y + play_size//2 + glow),
                        (center_x + play_size//2 + glow, center_y)
                    ]
                    # Note: PIL doesn't support alpha in polygon, so we'll use solid colors
                    glow_fill = (min(255, 100 + glow * 20), min(255, 150 + glow * 10), 255)
                    if glow <= 2:  # Only draw the inner bright layers
                        draw.polygon(triangle_points, fill=glow_fill, outline=(200, 200, 255))
                
                # Main play button
                triangle_points = [
                    (center_x - play_size//2, center_y - play_size//2),
                    (center_x - play_size//2, center_y + play_size//2),
                    (center_x + play_size//2, center_y)
                ]
                draw.polygon(triangle_points, fill=(255, 255, 255), outline=(220, 220, 255))
                
                # Add video text with style
                try:
                    font = ImageFont.truetype("assets/fonts/arial.ttf", 28)
                except:
                    font = ImageFont.load_default()
                
                video_text = "🎬 VIDEO"
                bbox = draw.textbbox((0, 0), video_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_x = (max_size[0] - text_width) // 2
                text_y = center_y + play_size//2 + 25
                
                # Text shadow
                draw.text((text_x + 2, text_y + 2), video_text, fill=(0, 0, 0), font=font)
                draw.text((text_x, text_y), video_text, fill=(255, 255, 255), font=font)
            
        else:
            # For images, process normally
            try:
                img = Image.open(io.BytesIO(response.content)).convert('RGB')
                img.thumbnail(max_size, Image.LANCZOS)
            except Exception as img_error:
                print(f"[THUMBNAIL] Image processing failed: {img_error}, creating placeholder")
                # Create placeholder for corrupted/unsupported images
                img = Image.new('RGB', max_size, (50, 50, 50))
                draw = ImageDraw.Draw(img)
                
                try:
                    font = ImageFont.truetype("assets/fonts/arial.ttf", 32)
                except:
                    font = ImageFont.load_default()
                
                placeholder_text = "IMAGE"
                bbox = draw.textbbox((0, 0), placeholder_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = (max_size[0] - text_width) // 2
                text_y = (max_size[1] - text_height) // 2
                
                draw.text((text_x, text_y), placeholder_text, fill=(255, 255, 255), font=font)
        
        # Save to temp directory
        filename = f"thumb_{hash(url) % 10000}.jpg"
        thumb_path = os.path.join(temp_dir, filename)
        img.save(thumb_path, 'JPEG', quality=90)
        
        return thumb_path
        
    except Exception as e:
        print(f"[THUMBNAIL] Failed to download {url}: {e}")
        # Create error placeholder
        try:
            img = Image.new('RGB', max_size, (80, 20, 20))
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("arial.ttf", 28)
            except:
                font = ImageFont.load_default()
            
            error_text = "MEDIA ERROR"
            bbox = draw.textbbox((0, 0), error_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (max_size[0] - text_width) // 2
            text_y = (max_size[1] - text_height) // 2
            
            draw.text((text_x, text_y), error_text, fill=(255, 255, 255), font=font)
            
            filename = f"error_thumb_{hash(url) % 10000}.jpg"
            thumb_path = os.path.join(temp_dir, filename)
            img.save(thumb_path, 'JPEG', quality=80)
            
            return thumb_path
        except:
            return None

def format_mentions(content, guild=None):
    """Convert Discord mention format to readable names."""
    # Format user mentions
    user_mentions = re.findall(r'<@!?(\d+)>', content)
    for user_id in user_mentions:
        if guild:
            member = guild.get_member(int(user_id))
            if member:
                display_name = member.display_name
                content = content.replace(f'<@{user_id}>', f'@{display_name}')
                content = content.replace(f'<@!{user_id}>', f'@{display_name}')
            else:
                content = content.replace(f'<@{user_id}>', f'@user')
                content = content.replace(f'<@!{user_id}>', f'@user')
        else:
            content = content.replace(f'<@{user_id}>', f'@user')
            content = content.replace(f'<@!{user_id}>', f'@user')
    
    # Format channel mentions: <#123456789>
    channel_mentions = re.findall(r'<#(\d+)>', content)
    for channel_id in channel_mentions:
        if guild:
            channel = guild.get_channel(int(channel_id))
            if channel:
                content = content.replace(f'<#{channel_id}>', f'#{channel.name}')
            else:
                content = content.replace(f'<#{channel_id}>', f'#channel')
        else:
            content = content.replace(f'<#{channel_id}>', f'#channel')
    
    # Format role mentions: <@&123456789>
    role_mentions = re.findall(r'<@&(\d+)>', content)
    for role_id in role_mentions:
        if guild:
            role = guild.get_role(int(role_id))
            if role:
                content = content.replace(f'<@&{role_id}>', f'@{role.name}')
            else:
                content = content.replace(f'<@&{role_id}>', f'@role')
        else:
            content = content.replace(f'<@&{role_id}>', f'@role')
            
    return content

async def generate_tts_for_message(text, user_id, temp_dir, has_media=False):
    """Generate TTS audio for a message using the user's assigned voice"""
    # If no text but has media, create 1s blank audio
    if (not text or not text.strip()) and has_media:
        blank_audio_path = os.path.join(temp_dir, f"blank_audio_{user_id}_{random.randint(1000,9999)}.wav")
        try:
            # Create 1 second of silence
            import subprocess
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=22050', 
                '-t', '1', '-y', blank_audio_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"[TTS] 🔇 Created 1s blank audio for image-only message")
            return blank_audio_path
        except Exception as e:
            print(f"[TTS] ⚠️ Failed to create blank audio: {e}")
            return None
    
    if not text or not text.strip():
        return None
    
    # Clean text for speech
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        return None
    
    # Get assigned voice for user
    voice = assign_voice_to_user(user_id)
    audio_path = os.path.join(temp_dir, f"tts_{user_id}_{hash(clean_text) % 10000}.mp3")
    
    try:
        # Try Edge TTS first (95% chance)
        if random.random() < 0.95:
            print(f"[TTS] Generating Edge TTS for user {user_id} with voice {voice}")
            communicate = edge_tts.Communicate(clean_text, voice)
            await communicate.save(audio_path)
            
            # Verify file was created
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                print(f"[TTS] ✅ Edge TTS succeeded for user {user_id}")
                return audio_path
            else:
                print(f"[TTS] ⚠️ Edge TTS failed for user {user_id}, trying gTTS")
        
        # Fallback to gTTS
        print(f"[TTS] Using gTTS fallback for user {user_id}")
        tts = gTTS(text=clean_text, lang='en', tld='com', slow=False)
        tts.save(audio_path)
        
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            print(f"[TTS] ✅ gTTS succeeded for user {user_id}")
            return audio_path
        else:
            print(f"[TTS] ❌ gTTS failed for user {user_id}")
            return None
            
    except Exception as e:
        print(f"[TTS] ❌ TTS generation failed for user {user_id}: {e}")
        return None

def get_text_size(draw, text, font):
    """
    Return the (width, height) of the given text using the provided font.
    Uses textsize if available; otherwise falls back to textbbox.
    """
    try:
        return draw.textsize(text, font=font)
    except AttributeError:
        bbox = draw.textbbox((0, 0), text, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

def fetch_avatar(avatar_url, size=(80,80)):
    """
    Download an avatar image from the given URL, resize it, and crop it to a circle.
    Returns a PIL Image with transparency.
    """
    try:
        response = requests.get(avatar_url)
        response.raise_for_status()
        avatar_img = Image.open(io.BytesIO(response.content)).convert("RGBA")
        avatar_img = avatar_img.resize(size)
        # Create a circular mask.
        mask = Image.new("L", size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size[0], size[1]), fill=255)
        avatar_img.putalpha(mask)
        return avatar_img
    except Exception as e:
        logging.error(f"Error fetching avatar: {e}")
        return None

def render_message_image_beautiful(username: str, message: str, avatar_url: str = None, width: int = 1280, 
                       height: int = 720, user_id: str = None, message_index: int = 0, 
                       total_messages: int = 1, media_paths: list = None, attachment_urls: list = None,
                       video_seed: int = None) -> Image.Image:
    """
    Render a next-level message image with dynamic effects and animations.
    
    Args:
        username: The username to display
        message: The message text
        avatar_url: URL to the user's avatar image
        width: Image width
        height: Image height
        user_id: User ID for voice assignment
        message_index: Current message index for animations
        total_messages: Total number of messages for progress
    """
    # Generate unique color palette for this user
    def generate_user_palette(user_id_str):
        # Use user ID to create deterministic but unique colors
        hash_val = hash(user_id_str or username) % 360
        hue = hash_val
        sat_base = 0.7 + (hash_val % 20) / 100  # 0.7-0.9
        
        # Primary color (user's theme color)
        primary_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue/360, sat_base, 0.85))
        
        # Secondary color (complementary)
        secondary_hue = (hue + 180) % 360
        secondary_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(secondary_hue/360, sat_base * 0.6, 0.9))
        
        # Accent color (triadic)
        accent_hue = (hue + 120) % 360
        accent_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(accent_hue/360, sat_base * 0.8, 0.95))
        
        return primary_color, secondary_color, accent_color
    
    primary_color, secondary_color, accent_color = generate_user_palette(user_id)
    
    # Animation time based on message index
    t = message_index * 0.5  # Half second per message for animation timing
    
    # UNIQUE generation effects - each video is completely different!
    if video_seed is None:
        video_seed = random.randint(1000, 9999)
    
    # Generate unique effects based on video seed
    random.seed(video_seed + message_index)
    
    # Random generation themes
    themes = ['cyber', 'neon', 'hologram', 'matrix', 'plasma', 'crystal']
    theme = themes[video_seed % len(themes)]
    
    # Unique animation patterns per generation
    animation_style = video_seed % 4
    base_speed = 1.0 + (video_seed % 100) / 200.0  # 1.0 to 1.5 speed multiplier
    
    # Adjust animation timing with unique factors
    t = t * base_speed + (video_seed % 1000) / 1000.0
    
    def create_dynamic_gradient(width, height, t):
        """Create smooth animated gradient background without harsh transitions"""
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)
        
        # Base gradient colors (more subtle)
        grad_color1 = tuple(max(25, min(255, c - 30)) for c in primary_color)
        grad_color2 = tuple(max(15, min(200, c - 50)) for c in secondary_color)
        
        for y in range(height):
            # Create smooth vertical gradient
            base_ratio = y / height
            
            # Add gentle wave animation without discontinuous jumps
            wave_offset = 0.03 * math.sin(2 * math.pi * y / 120 + t * 1.5)
            time_shift = 0.02 * math.sin(t * 0.9)  # Gentle time-based variation
            
            # Combine effects smoothly
            ratio = base_ratio + wave_offset + time_shift
            ratio = max(0, min(1, ratio))  # Clamp to [0,1]
            
            # Smooth color interpolation
            r = int(grad_color1[0] * (1 - ratio) + grad_color2[0] * ratio)
            g = int(grad_color1[1] * (1 - ratio) + grad_color2[1] * ratio)
            b = int(grad_color1[2] * (1 - ratio) + grad_color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        return img
    
    # Create dynamic background
    bg = create_dynamic_gradient(width, height, t)
    
    # Add floating particles effect
    def add_floating_particles(img, t, count=15):
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        for i in range(count):
            phase = i * 0.628 + hash(username or "") % 100
            x = (width * 0.1 + (width * 0.8) * ((t * 0.5 + phase) % 1)) % width
            y = height * 0.1 + (height * 0.8) * ((t * 0.3 + phase * 1.3) % 1)
            x += 20 * math.sin(t + phase)
            y += 15 * math.cos(t * 0.8 + phase * 1.2)
            
            size = abs(2 + 3 * math.sin(t * 2 + phase))  # Ensure positive size
            alpha = int(60 + 40 * math.sin(t * 1.5 + phase))
            color = (*accent_color, max(0, min(255, alpha)))
            # Ensure valid ellipse coordinates
            x1, y1 = max(0, x - size), max(0, y - size)
            x2, y2 = min(width, x + size), min(height, y + size)
            
            if x2 > x1 and y2 > y1:  # Only draw if coordinates are valid
                draw.ellipse([x1, y1, x2, y2], fill=color)
        
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=4))
        return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    
    bg = add_floating_particles(bg, t)
    
    # Load fonts
    def load_font(path_candidates, size):
        for p in path_candidates:
            if os.path.exists(p):
                try:
                    font = ImageFont.truetype(p, size)
                    print(f"[FONT] Bold font loaded: {p}")
                    return font
                except Exception as e:
                    print(f"[FONT] Failed to load bold font {p}: {e}")
                    pass
        print(f"[FONT] Using default bold font (size {size})")
        return ImageFont.load_default()
    
    def load_emoji_supporting_font(size):
        """Load font that supports emojis, with fallbacks from assets folder"""
        # Priority order: GUARANTEED emoji/Unicode supporting fonts first!
        font_candidates = [
            # 🏆 TIER 1: GUARANTEED EMOJI SUPPORT
            "assets/fonts/seguiemj.ttf",         # 🥇 Segoe UI Emoji - WINDOWS EMOJI FONT!
            "assets/fonts/SegUIVar.ttf",         # 🥈 Segoe UI Variable (Windows 11 emoji)
            "assets/fonts/seguisym.ttf",         # 🥉 Segoe UI Symbol (symbols + emojis)
            
            # 🏅 TIER 2: EXCELLENT UNICODE SUPPORT
            "assets/fonts/unicode.impact.ttf",   # Unicode Impact (custom Unicode build)
            "assets/fonts/segoeui.ttf",          # Segoe UI (modern Windows font)
            "assets/fonts/segoeuib.ttf",         # Segoe UI Bold
            "assets/fonts/segoeuii.ttf",         # Segoe UI Italic
            "assets/fonts/Nirmala.ttc",          # Nirmala UI (great Unicode support)
            
            # 🏅 TIER 3: ASIAN FONTS (EXCELLENT UNICODE)
            "assets/fonts/malgun.ttf",           # Malgun Gothic (Korean Unicode)
            "assets/fonts/malgunbd.ttf",         # Malgun Gothic Bold
            "assets/fonts/msyh.ttc",             # Microsoft YaHei (Chinese Unicode)
            "assets/fonts/msyhbd.ttc",           # Microsoft YaHei Bold
            "assets/fonts/msjh.ttc",             # Microsoft JhengHei (Traditional Chinese)
            "assets/fonts/YuGothR.ttc",          # Yu Gothic Regular (Japanese)
            "assets/fonts/YuGothB.ttc",          # Yu Gothic Bold
            
            # 🏅 TIER 4: MODERN SYSTEM FONTS
            "assets/fonts/calibri.ttf",          # Calibri (modern, good Unicode)
            "assets/fonts/calibrib.ttf",         # Calibri Bold
            "assets/fonts/Candara.ttf",          # Candara (modern design)
            "assets/fonts/corbel.ttf",           # Corbel (Windows Vista+)
            "assets/fonts/tahoma.ttf",           # Tahoma (excellent Unicode)
            "assets/fonts/tahomabd.ttf",         # Tahoma Bold
            "assets/fonts/verdana.ttf",          # Verdana (web-safe Unicode)
            "assets/fonts/georgia.ttf",          # Georgia (good Unicode)
            "assets/fonts/trebuc.ttf",           # Trebuchet MS
            
            # 🏅 TIER 5: CENTRAL EUROPEAN (UNICODE VARIANTS)
            "assets/fonts/ArialCE.ttf",          # Arial Central European 
            "assets/fonts/ArialCEBoldItalic.ttf",
            "assets/fonts/ArialCEItalic.ttf",
            "assets/fonts/ArialCEMTBlack.ttf",
            "assets/fonts/arialceb.ttf",
            
            # 🏅 TIER 6: STANDARD FONTS (FALLBACK)
            "assets/fonts/arial.ttf",            # Standard Arial
            "assets/fonts/times.ttf",            # Times New Roman
            "assets/fonts/ARIALN.TTF",           # Arial Narrow
            "assets/fonts/impact.ttf",           # Impact
            "assets/fonts/Impacted.ttf"          # Impact variant
        ]
        
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, size)
                    # Test if this font can actually render emojis
                    emoji_supported = test_emoji_support(font)
                    tier = "🏆 TIER 1" if "seguiemj" in font_path or "SegUIVar" in font_path or "seguisym" in font_path else \
                           "🏅 TIER 2+" if any(x in font_path for x in ["segoeui", "unicode", "Nirmala"]) else \
                           "🏅 TIER 3+" if any(x in font_path for x in ["malgun", "msyh", "YuGoth"]) else \
                           "🏅 TIER 4+"
                    print(f"[FONT] ✅ {tier} LOADED: {font_path}")
                    print(f"[FONT]    └─ Emoji support: {'🎨 EXCELLENT' if emoji_supported else '⚠️  LIMITED'}")
                    return font
                except Exception as e:
                    print(f"[FONT] Failed to load {font_path}: {e}")
                    continue
        
        print(f"[FONT] Using default font (size {size})")
        return ImageFont.load_default()
    
    def test_emoji_support(font, test_emoji="😊"):
        """Test if a font can render emojis properly"""
        try:
            # Try to get text bounding box for an emoji
            test_img = Image.new('RGB', (100, 100), (255, 255, 255))
            test_draw = ImageDraw.Draw(test_img)
            bbox = test_draw.textbbox((0, 0), test_emoji, font=font)
            # If bbox is valid and has width/height, emoji is supported
            return bbox[2] > bbox[0] and bbox[3] > bbox[1]
        except Exception:
            return False

    bold_font = load_font([
        "assets/fonts/arialbd.ttf", "assets/fonts/ARIALBD 1.TTF", "assets/fonts/ARIALNB.TTF"
    ], 52)
    regular_font = load_emoji_supporting_font(36)  # Use emoji-supporting font for regular text
    
    # PROPER DISCORD-LIKE LAYOUT - Define positions first 🔥
    avatar_x = 30  # Left margin for avatar
    avatar_y = 30  # Top margin  
    avatar_size = 100  # Standard Discord size
    x_offset = avatar_x + avatar_size + 20  # Text starts right of avatar + spacing
    y_offset = avatar_y  # Text starts at same height as avatar
    
    # Simple clean avatar placement (Discord style)
    if avatar_url:
        try:
            avatar_img = fetch_avatar(avatar_url, size=(avatar_size, avatar_size))
            if avatar_img:
                # Simple clean placement - no fancy animations that break alignment
                bg.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
        except Exception as e:
            logging.error(f"Error processing avatar: {e}")
    
    # Progress indicator
    if total_messages > 1:
        progress = message_index / max(1, total_messages - 1)
        progress_bar_width = width - 100
        progress_x, progress_y = 50, height - 30
        
        bg_img = Image.new('RGBA', bg.size, (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_img)
        bg_draw.rounded_rectangle([progress_x, progress_y, progress_x + progress_bar_width, progress_y + 6], 
                                 radius=3, fill=(255, 255, 255, 60))
        
        current_progress = int(progress_bar_width * progress)
        if current_progress > 0:
            bg_draw.rounded_rectangle([progress_x, progress_y, progress_x + current_progress, progress_y + 6], 
                                     radius=3, fill=(*accent_color, 180))
        
        bg = Image.alpha_composite(bg.convert('RGBA'), bg_img).convert('RGB')
    
    # Clean media display (Discord style - no overlap!)
    media_display_height = 0
    text_start_y = y_offset + 60  # Start below username
    
    # Handle media attachments cleanly
    if media_paths and len(media_paths) > 0:
        for media_path in media_paths[:1]:  # Show only first media to prevent overlap
            try:
                if os.path.exists(media_path):
                    # Load and resize media properly
                    media_img = Image.open(media_path).convert('RGB')
                    
                    # Proper sizing like Discord
                    max_img_width = width - x_offset - 40
                    max_img_height = 250  # Reasonable height
                    
                    img_width, img_height = media_img.size
                    scale = min(max_img_width/img_width, max_img_height/img_height)
                    new_width = int(img_width * scale)
                    new_height = int(img_height * scale)
                    
                    media_img = media_img.resize((new_width, new_height), Image.LANCZOS)
                    
                    # Position media BELOW username, ABOVE text
                    media_x = x_offset
                    media_y = text_start_y
                    
                    # Simple rounded background
                    padding = 5
                    bg_img = Image.new("RGBA", (new_width + padding*2, new_height + padding*2), (240, 240, 250, 200))
                    mask = Image.new("L", (new_width + padding*2, new_height + padding*2), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.rounded_rectangle((0, 0, new_width + padding*2, new_height + padding*2), radius=10, fill=255)
                    
                    # Paste media onto background
                    bg_img.paste(media_img, (padding, padding))
                    bg.paste(bg_img, (media_x, media_y), mask=mask)
                    
                    # Update text position to be BELOW media
                    text_start_y = media_y + new_height + padding*2 + 15
                    media_display_height = new_height + padding*2 + 15
            except Exception as e:
                print(f"[MEDIA] Error processing {media_path}: {e}")
    
    # Layout positions already defined above
    
    # Get text dimensions helper (from your OG code)
    def get_text_size(draw, text, font):
        try:
            return draw.textsize(text, font=font)
        except AttributeError:
            bbox = draw.textbbox((0, 0), text, font=font)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    
    # Username positioning (TOP-LEFT aligned)
    username_x = x_offset
    username_y = y_offset
    
    # text_start_y is already calculated above in media section
    text_width = width - x_offset - 40  # Leave margin for screen edge
    
    # LIQUID GLASS BUBBLE - exactly like your beautiful OG design
    if message.strip():  # Only create bubble if there's text
        # Smart word wrapping from your OG code
        words = message.split()
        lines = []
        current_line = ""
        max_text_width = text_width - 80  # Account for bubble padding
        
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            w, _ = get_text_size(temp_draw, test_line, regular_font)
            if w <= max_text_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Calculate perfect bubble dimensions
        line_height = get_text_size(temp_draw, "Tg", regular_font)[1] + 5
        bubble_height = (len(lines) * line_height) + 30
        bubble_width = min(max(get_text_size(temp_draw, line, regular_font)[0] for line in lines) + 40, max_text_width) if lines else 200
        
        # LIQUID GLASS BUBBLE - your gorgeous OG style
        bubble_x = x_offset
        bubble_y = text_start_y
        bubble_radius = 20
        
        # Create the liquid glass effect
        bubble_img = Image.new('RGBA', bg.size, (0, 0, 0, 0))
        bubble_draw = ImageDraw.Draw(bubble_img)
        
        # ACTUAL LIQUID GLASS EFFECT with background blur 🌟
        # First, get the background behind the bubble
        bubble_bg = bg.crop((bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height))
        bubble_bg = bubble_bg.filter(ImageFilter.GaussianBlur(radius=3))  # Soft blur
        
        # Create glass effect with transparency that shows RGB background
        glass_overlay = Image.new('RGBA', (bubble_width, bubble_height), (255, 255, 255, 120))  # Semi-transparent white
        glass_mask = Image.new('L', (bubble_width, bubble_height), 0)
        glass_mask_draw = ImageDraw.Draw(glass_mask)
        glass_mask_draw.rounded_rectangle((0, 0, bubble_width, bubble_height), radius=bubble_radius, fill=255)
        
        # Blend blurred background with glass overlay
        bubble_bg = bubble_bg.convert('RGBA')
        glass_bubble = Image.alpha_composite(bubble_bg, glass_overlay)
        
        # Add subtle frosted effect
        frosted = Image.new('RGBA', (bubble_width, bubble_height), (255, 255, 255, 40))
        glass_bubble = Image.alpha_composite(glass_bubble, frosted)
        
        # Add subtle accent border for definition
        border_overlay = Image.new('RGBA', (bubble_width, bubble_height), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_overlay)
        border_color = (*accent_color, 100)  # Soft accent border
        border_draw.rounded_rectangle((0, 0, bubble_width, bubble_height), radius=bubble_radius, outline=border_color, width=2)
        glass_bubble = Image.alpha_composite(glass_bubble, border_overlay)
        
        # Paste the liquid glass bubble back
        bg.paste(glass_bubble, (bubble_x, bubble_y), mask=glass_mask)
        
        # Apply liquid glass to background
        bg = Image.alpha_composite(bg.convert('RGBA'), bubble_img)
        
        # Text inside bubble (clean like your OG)
        text_img = Image.new('RGBA', bg.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)
        
        text_x = bubble_x + 20
        text_y = bubble_y + 15
        text_color = (40, 40, 40)  # Clean dark text like your OG
        
        for line in lines:
            text_draw.text((text_x, text_y), line, fill=text_color, font=regular_font)
            text_y += line_height
        
        # Composite text
        bg = Image.alpha_composite(bg, text_img)
    
    # Username with clean style (like your OG - outside bubble)
    username_img = Image.new('RGBA', bg.size, (0, 0, 0, 0))
    username_draw = ImageDraw.Draw(username_img)
    
    # Username with subtle shadow and user's theme color
    username_shadow = (0, 0, 0, 100)
    username_draw.text((username_x + 2, username_y + 2), username, fill=username_shadow, font=bold_font)
    username_draw.text((username_x, username_y), username, fill=primary_color, font=bold_font)
    
    # Composite username
    bg = Image.alpha_composite(bg, username_img).convert('RGB')
    
    # Bot display avatar in top right corner (ACTUAL bot avatar!)
    try:
        # Get the bot avatar from Discord API
        bot_avatar_size = 60
        bot_x = width - bot_avatar_size - 20
        bot_y = 20
        
        # Use local bot avatar from assets folder
        try:
            # Try to load bot avatar from local assets (prefer gif over jpg)
            import os
            
            # Try different avatar files in order of preference
            avatar_files = ["avatar.gif", "avatar.jpg", "avatar-crop.gif"]
            bot_avatar_path = None
            
            for avatar_file in avatar_files:
                # Try relative to this file
                path1 = os.path.join(os.path.dirname(__file__), "..", "..", "assets", avatar_file)
                # Try from working directory  
                path2 = os.path.join("assets", avatar_file)
                
                if os.path.exists(path1):
                    bot_avatar_path = path1
                    break
                elif os.path.exists(path2):
                    bot_avatar_path = path2
                    break
            
            if bot_avatar_path and os.path.exists(bot_avatar_path):
                bot_avatar_img = Image.open(bot_avatar_path).convert("RGBA")
                bot_avatar_img = bot_avatar_img.resize((bot_avatar_size, bot_avatar_size), Image.LANCZOS)
                
                # Create circular mask for bot avatar
                mask = Image.new("L", (bot_avatar_size, bot_avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, bot_avatar_size, bot_avatar_size), fill=255)
                bot_avatar_img.putalpha(mask)
                
                # Add subtle glow around bot avatar
                glow = Image.new("RGBA", (bot_avatar_size + 10, bot_avatar_size + 10), (0, 0, 0, 0))
                glow_draw = ImageDraw.Draw(glow)
                glow_draw.ellipse((0, 0, bot_avatar_size + 10, bot_avatar_size + 10), fill=(100, 150, 255, 80))
                
                # Paste glow then avatar
                bg.paste(glow, (bot_x - 5, bot_y - 5), mask=glow)
                bg.paste(bot_avatar_img, (bot_x, bot_y), mask=bot_avatar_img)
            else:
                raise Exception("Bot avatar file not found")
                
        except Exception:
            # Fallback: Simple bot indicator circle
            bot_img = Image.new('RGBA', bg.size, (0, 0, 0, 0))
            bot_draw = ImageDraw.Draw(bot_img)
            
            # Simple bot indicator
            bot_color = (100, 150, 255, 200)  # Bot blue color
            bot_draw.ellipse([bot_x, bot_y, bot_x + bot_avatar_size, bot_y + bot_avatar_size], fill=bot_color)
            
            # Add "BOT" text
            try:
                bot_font = load_emoji_supporting_font(12)
                text_w, text_h = get_text_size(bot_draw, "BOT", bot_font)
                text_x = bot_x + (bot_avatar_size - text_w) // 2
                text_y = bot_y + (bot_avatar_size - text_h) // 2
                bot_draw.text((text_x, text_y), "BOT", fill=(255, 255, 255), font=bot_font)
            except:
                pass
            
            bg = Image.alpha_composite(bg.convert('RGBA'), bot_img).convert('RGB')
            
    except Exception as e:
        print(f"[BOT AVATAR] Error: {e}")
    
    return bg

def generate_video_from_images(image_paths: list, fps: float = 1.0) -> io.BytesIO:
    """
    Use FFmpeg to combine a sequence of images into a video.
    
    Args:
        image_paths: List of paths to image files
        fps: Frames per second (controls video speed)
    
    Returns:
        io.BytesIO: Buffer containing the video data
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        output_video = os.path.join(temp_dir, "video.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate", str(fps),
            "-i", os.path.join(os.path.dirname(image_paths[0]), "frame_%03d.png"),
            "-c:v", "libx264",
            "-preset", "ultrafast",  # fast boi
            "-crf", "23",         # Better quality-to-size ratio
            "-pix_fmt", "yuv420p",
            "-vf", "fade=t=in:st=0:d=0.5,fade=t=out:st=" + str(len(image_paths)/fps - 0.5) + ":d=0.5",  # Add fade in/out
            output_video
        ]
        logging.info("Running FFmpeg to generate video...")
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        final_video = output_video
        sound_effect_path = os.path.join(os.path.dirname(__file__), "assets", "sound_effect.mp3")
        if os.path.exists(sound_effect_path):
            final_video = os.path.join(temp_dir, "final.mp4")
            cmd_audio = [
                "ffmpeg",
                "-y",
                "-i", output_video,
                "-i", sound_effect_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                final_video
            ]
            logging.info("Overlaying audio with FFmpeg...")
            subprocess.run(cmd_audio, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        with open(final_video, "rb") as f:
            video_data = f.read()
        return io.BytesIO(video_data)

async def generate_meme_video_nextlevel(messages: list, duration: float = None, progress_msg=None, guild=None) -> io.BytesIO:
    """
    Generate a next-level meme video from Discord messages with voiceovers and enhanced visuals.
    
    Args:
        messages (list): List of dicts with message data.
        duration (float): Total duration of the video in seconds. If None, calculated dynamically from audio.
        progress_msg: Discord message object for progress updates (optional).
        guild: Discord guild object to determine upload limits based on boost level.
    
    Returns:
        io.BytesIO: Buffer containing the final video with voiceovers.
    """
    
    # Determine upload limit based on server boost level
    def get_upload_limit(guild):
        if guild is None:
            return 10  # Default bot limit in MB
        
        boost_level = guild.premium_tier
        if boost_level >= 3:
            return 100  # Level 3: 100MB
        elif boost_level >= 2:
            return 50   # Level 2: 50MB
        else:
            return 10   # Level 0-1: 10MB (bot default)
    
    upload_limit_mb = get_upload_limit(guild)
    
    # Set maximum duration based on server boost level to prevent massive files
    def get_max_duration(guild):
        if guild is None:
            return 180  # 3 minutes for unknown servers
        
        boost_level = guild.premium_tier
        if boost_level >= 3:
            return 600  # Level 3: 10 minutes max
        elif boost_level >= 2:
            return 360  # Level 2: 6 minutes max  
        else:
            return 180  # Level 0-1: 3 minutes max
    
    max_duration_seconds = get_max_duration(guild)
    boost_level = guild.premium_tier if guild else 0
    print(f"[VIDEO] 📊 Server boost level: {boost_level}, Upload limit: {upload_limit_mb}MB, Max duration: {max_duration_seconds//60}min")
    
    # Create server info message for user notification
    def get_server_info_message(boost_level, upload_limit_mb, max_duration_seconds):
        if boost_level >= 3:
            return (
                f"🌟 **Premium Server** (Level {boost_level})\n"
                f"📊 **Quality**: Ultra High | **Max Messages**: 250 | **File Limit**: {upload_limit_mb}MB\n"
                f"🎬 Enjoy the best video quality!"
            )
        elif boost_level >= 2:
            return (
                f"🚀 **Boosted Server** (Level {boost_level})\n"
                f"📊 **Quality**: High | **Max Messages**: 125 | **File Limit**: {upload_limit_mb}MB\n"
                f"✨ Great video quality! Consider Level 3 for even better results."
            )
        else:
            return (
                f"📱 **Standard Server** (Level {boost_level})\n"
                f"📊 **Quality**: Standard | **Max Messages**: 25 | **File Limit**: {upload_limit_mb}MB\n"
                f"💎 **Want better?** Ask admins to boost this server for:\n"
                f"   • Level 2: 125 messages, 50MB limit\n"
                f"   • Level 3: 250 messages, 100MB limit"
            )
    
    server_info = get_server_info_message(boost_level, upload_limit_mb, max_duration_seconds)
    
    async def update_progress(percentage, status_text):
        """Helper function to update progress message with better error handling"""
        print(f"[PROGRESS] {percentage}% - {status_text}")
        if progress_msg:
            try:
                # Force await the edit operation
                import asyncio
                await asyncio.sleep(0.1)  # Give Discord API a moment
                await progress_msg.edit(content=f"🎬 **Generating chat video...** \n{server_info}\n\n⏳ **Progress:** {percentage}% - {status_text}")
                print(f"[PROGRESS] ✅ Discord message updated successfully: {percentage}%")
                await asyncio.sleep(0.1)  # Prevent rate limiting
            except Exception as e:
                print(f"[PROGRESS] ⚠️ Failed to update Discord message: {e}")
                # Continue anyway
    if not messages or not isinstance(messages, list):
        raise ValueError("No messages provided or messages is not a list.")
    
    # MEMORY SAFETY: Check initial memory usage
    initial_memory = get_memory_usage()
    print(f"[MEMORY] 💾 Initial memory usage: {initial_memory:.1f}MB")
    
    # Safety check for Railway's 512MB HARD LIMIT (90% = 460MB)
    if initial_memory > 350:  # If already using > 350MB (68% of limit)
        print(f"[MEMORY] ⚠️ HIGH INITIAL MEMORY: {initial_memory:.1f}MB - forcing cleanup before starting")
        force_memory_cleanup()
        initial_memory = get_memory_usage()
        print(f"[MEMORY] 💾 Memory after cleanup: {initial_memory:.1f}MB")
        
        # If still high after cleanup, reduce message count to prevent OOM
        if initial_memory > 300:
            message_reduction = max(1, int(initial_memory / 40))  # More aggressive reduction
            messages = messages[:max(3, len(messages) // message_reduction)]
            print(f"[MEMORY] 🔥 SAFETY: Reduced to {len(messages)} messages due to memory constraints")
    
    # EMERGENCY BAILOUT: If memory is critically high, abort
    if initial_memory > 450:  # 88% of 512MB limit
        raise RuntimeError(f"❌ MEMORY CRITICAL: {initial_memory:.1f}MB exceeds safe limit (450MB). Bot restart required.")
    
    print(f"[VIDEO] 🎬 Generating next-level meme video with {len(messages)} messages")
    
    # Clear voice assignments for fresh video
    global user_voice_assignments
    user_voice_assignments.clear()
    
    # Filter and prepare messages
    valid_messages = []
    for msg in messages:
            if not isinstance(msg, dict) or "name" not in msg or "message" not in msg:
                continue
            
            username = msg["name"]
            text = msg["message"]
            user_id = msg.get("user_id", username)  # Use user_id if available, fallback to username
            
            # Format mentions if guild is available
            if "guild" in msg:
                text = format_mentions(text, msg["guild"])
            
            # Extract media links for thumbnail generation
            media_links = extract_media_links(text)
            
            # Clean text for speech
            clean_text = clean_text_for_speech(text)
            if clean_text or media_links or msg.get("avatar"):  # Include if has speakable content, media, or attachments
                valid_messages.append({
                    "username": username,
                    "message": text,
                    "clean_message": clean_text,
                    "avatar_url": msg.get("avatar"),
                    "user_id": user_id,
                    "media_links": media_links,
                    "attachment_urls": msg.get("attachment_urls", [])
                })
    
    if not valid_messages:
        raise ValueError("No valid messages with speakable content found.")
    
    print(f"[VIDEO] ✅ Filtered to {len(valid_messages)} speakable messages")
    
    # Only limit by estimated file size, not duration - let users enjoy longer videos!
    # Calculate maximum messages based on server boost level (for file size, not duration)
    max_messages_by_level = {
        0: 25,  # Level 0: max 25 messages (targeting ~8-9MB)
        1: 25,  # Level 1: max 25 messages  
        2: 125, # Level 2: max 125 messages (targeting ~45MB)
        3: 250  # Level 3: max 250 messages (targeting ~90MB)
    }
    
    boost_level = guild.premium_tier if guild else 0
    max_messages = max_messages_by_level.get(boost_level, 40)
    
    # Limit by message count to target file size (not duration)
    if len(valid_messages) > max_messages:
        valid_messages = valid_messages[:max_messages]
        print(f"[VIDEO] ⚠️ Trimmed to {len(valid_messages)} messages to target file size for Level {boost_level}")
    
    # Update progress with server info - starting image and audio generation
    await update_progress(13, f"Rendering {len(valid_messages)} messages")
    
    # Send server boost info to user
    if progress_msg:
        try:
            await progress_msg.edit(content=f"🎬 **Generating chat video...** \n⏳ **Progress:** 13% - Rendering messages\n\n{server_info}")
        except Exception as e:
            print(f"[PROGRESS] ⚠️ Failed to update progress with server info: {e}")
    
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"[VIDEO] 🎨 Generating images and TTS audio...")
        
        # Generate unique video seed for this generation
        video_seed = random.randint(10000, 99999)
        print(f"[VIDEO] 🎲 Video generation seed: {video_seed}")
        
        # Generate images and TTS audio concurrently  
        # STREAMING APPROACH: Collect frame data instead of video clips
        frame_data_list = []
        video_clips = []  # Keep for fallback compatibility
        
        for i, msg in enumerate(valid_messages):
            print(f"[VIDEO] Processing message {i+1}/{len(valid_messages)}: {msg['username']}")
            
            # Update progress for each message processed
            current_percentage = 13 + int((i / len(valid_messages)) * 56)  # 13% to 69% range
            await update_progress(current_percentage, f"Rendering {i+1}/{len(valid_messages)}")
            
            # Yield control to prevent blocking Discord heartbeat
            import asyncio
            await asyncio.sleep(0.01)  # Brief yield
            
            # Download media thumbnails
            media_paths = []
            if msg.get("media_links"):
                for link in msg["media_links"]:
                    if link.get("thumbnail_url"):
                        thumb_path = await download_thumbnail(link["thumbnail_url"], temp_dir)
                        if thumb_path:
                            media_paths.append(thumb_path)
            
            # Process attachment URLs (from Discord attachments) 
            attachment_paths = []
            if msg.get("attachment_urls"):
                for url in msg["attachment_urls"]:
                    try:
                        # Download attachment
                        attachment_path = await download_thumbnail(url, temp_dir)
                        if attachment_path:
                            attachment_paths.append(attachment_path)
                            print(f"[VIDEO] 📎 Downloaded attachment: {url}")
                    except Exception as e:
                        print(f"[VIDEO] ⚠️ Failed to download attachment {url}: {e}")
            
            # Also check image_url for direct attachment
            if msg.get("image_url") and msg["image_url"] not in [link.get("thumbnail_url") for link in msg.get("media_links", [])]:
                try:
                    direct_image_path = await download_thumbnail(msg["image_url"], temp_dir)
                    if direct_image_path:
                        attachment_paths.append(direct_image_path)
                        print(f"[VIDEO] 🖼️ Downloaded direct image: {msg['image_url']}")
                except Exception as e:
                    print(f"[VIDEO] ⚠️ Failed to download direct image {msg['image_url']}: {e}")
            
            # Combine all media paths for rendering
            all_media_paths = media_paths + attachment_paths
            
            # Generate next-level image with ALL media and unique seed
            # Use cleaned display text for visual (preserves emojis)
            display_text = clean_text_for_display(msg["message"])
            
            # Yield before heavy image generation
            await asyncio.sleep(0.05)
            
            img = render_message_image_beautiful(
                username=msg["username"],
                message=display_text,  # Use cleaned display text
                avatar_url=msg["avatar_url"],
                user_id=msg["user_id"],
                message_index=i,
                total_messages=len(valid_messages),
                media_paths=all_media_paths,  # Use ALL media paths
                attachment_urls=msg.get("attachment_urls", []),
                video_seed=video_seed
            )
            
            # Yield after image generation
            await asyncio.sleep(0.05)
            
            image_path = os.path.join(temp_dir, f"frame_{i:03d}.png")
            img.save(image_path)
            
            # MEMORY OPTIMIZATION: Clean up large PIL image immediately after saving
            del img
            force_memory_cleanup()
            
            # Generate TTS audio - include image-only messages with blank audio
            audio_path = None
            has_media = bool(msg.get("media_paths") or msg.get("attachment_urls"))
            
            if msg["clean_message"] or has_media:  # If text OR media
                audio_path = await generate_tts_for_message(
                    msg["clean_message"], 
                    msg["user_id"], 
                    temp_dir,
                    has_media=has_media
                )
                if has_media and not msg["clean_message"]:
                    print(f"[VIDEO] 🖼️ Image-only message with 1s blank audio")
            else:
                print(f"[VIDEO] ⏭️ Skipping message with no content or media: {msg['message'][:50]}")
            
            # Calculate display duration with precise sync
            if audio_path and os.path.exists(audio_path):
                # Get EXACT audio duration for perfect sync
                try:
                    from moviepy.editor import AudioFileClip
                    audio_clip = AudioFileClip(audio_path)
                    # Use EXACT audio duration with minimal buffer to prevent drift
                    display_duration = audio_clip.duration + 0.1  # Minimal buffer
                    audio_clip.close()
                    print(f"[VIDEO] 🎵 Audio duration: {display_duration:.2f}s")
                except Exception as e:
                    print(f"[VIDEO] ⚠️ Error reading audio duration: {e}")
                    display_duration = max(2.0, len(msg["clean_message"]) * 0.1)
            else:
                # No audio - shorter duration for emoji/visual-only content
                if is_emoji_only(msg["message"]):
                    display_duration = 1.5  # Quick display for emojis
                else:
                    display_duration = max(2.0, len(msg["message"]) * 0.08)
                print(f"[VIDEO] 📱 No audio, visual duration: {display_duration:.2f}s")
            
            # Create video clip with async yields to prevent heartbeat blocking
            try:
                from moviepy.editor import ImageClip, AudioFileClip, CompositeAudioClip
                
                # Yield before heavy MoviePy operations
                await asyncio.sleep(0.1)
                
                image_clip = ImageClip(image_path).set_duration(display_duration)
                
                # Yield after image clip creation
                await asyncio.sleep(0.05)
                
                if audio_path and os.path.exists(audio_path):
                    audio_clip = AudioFileClip(audio_path)
                    # Ensure audio doesn't exceed image duration
                    if audio_clip.duration > display_duration:
                        audio_clip = audio_clip.subclip(0, display_duration)
                    
                    # Yield before audio attachment (heavy operation)
                    await asyncio.sleep(0.05)
                    image_clip = image_clip.set_audio(audio_clip)
                
                # STREAMING APPROACH: Store frame data instead of creating video clips
                frame_data_list.append((image_path, audio_path, display_duration))
                print(f"[VIDEO] 📹 Collected frame {i+1} (duration: {display_duration:.1f}s)")
                
                # MEMORY OPTIMIZATION: Don't keep video clips in memory
                # video_clips.append(image_clip)  # Commented out for streaming
                
                # Still keep cleanup every 3 frames for more aggressive memory management
                if (i + 1) % 3 == 0:
                    force_memory_cleanup()
                    memory_current = get_memory_usage()
                    print(f"[MEMORY] 💾 Memory after {i+1} frames: {memory_current:.1f}MB")
                    
                    # More aggressive safety check for 512MB limit (90% = 460MB)
                    if memory_current > 300:  # If over 300MB (59% of limit) 
                        print(f"[MEMORY] ⚠️ MEMORY WARNING: {memory_current:.1f}MB - forcing aggressive cleanup")
                        force_memory_cleanup()
                        
                    # CRITICAL: Abort if approaching limit
                    if memory_current > 400:  # 78% of 512MB limit
                        print(f"[MEMORY] 🚨 CRITICAL MEMORY: {memory_current:.1f}MB - stopping frame processing")
                        break
                
                # Yield after frame processing
                await asyncio.sleep(0.05)
                
            except Exception as e:
                print(f"[VIDEO] ❌ Error creating clip {i+1}: {e}")
                # Fallback: add frame data without audio
                await asyncio.sleep(0.05)
                frame_data_list.append((image_path, None, 2.0))  # 2 second fallback duration
                print(f"[VIDEO] 📹 Collected fallback frame {i+1} (2.0s)")
                await asyncio.sleep(0.05)
        
        if not frame_data_list:
            raise ValueError("No frames were generated.")
        
        print(f"[VIDEO] 🌊 Streaming {len(frame_data_list)} frames to FFmpeg...")
        
        # Update progress - video assembly
        await update_progress(69, "Assembling video")
        
        # Yield before heavy video assembly
        await asyncio.sleep(0.2)
        
        # STREAMING APPROACH: Use FFmpeg directly instead of MoviePy concatenation
        try:
            print(f"[VIDEO] 🌊 Starting STREAMING video creation with {len(frame_data_list)} frames...")
            memory_before = get_memory_usage()
            print(f"[MEMORY] 💾 Memory usage before streaming: {memory_before:.1f}MB")
            
            # Use our streaming FFmpeg function
            output_path = os.path.join(temp_dir, "final_video.mp4")
            
            # Calculate bitrates based on upload limits (same logic as before)
            upload_limit_mb = get_upload_limit(guild)
            target_size_mb = upload_limit_mb * 0.99
            target_size_bits = target_size_mb * 1024 * 1024 * 8
            
            # Estimate total duration
            total_duration = sum(duration for _, _, duration in frame_data_list)
            
            # MAIN PIPELINE: 720p ultrafast with CRF for optimal quality/size ratio
            audio_bitrate = 96  # 96k audio
            # Use CRF instead of fixed bitrate for better quality/size ratio
            print(f"[VIDEO] 🎬 STREAMING PIPELINE: 720p ultrafast + {audio_bitrate}k audio (CRF optimized)")
            
            # Stream frames to FFmpeg with CRF optimization
            await asyncio.get_event_loop().run_in_executor(
                None, 
                create_video_streaming_ffmpeg,
                frame_data_list,
                output_path,
                audio_bitrate,
                None,  # video_bitrate=None means use CRF
                24  # fps
            )
            
            memory_after = get_memory_usage()
            print(f"[VIDEO] ✅ Streaming complete. Memory: {memory_before:.1f}MB → {memory_after:.1f}MB")
            
            # No duration limits - let users enjoy their full videos!
            print(f"[VIDEO] 🎬 Video duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
            
            # Yield after streaming assembly
            await asyncio.sleep(0.2)
            
            # Note: Fade transitions handled directly in FFmpeg streaming process
            
            # Update progress - streaming export complete
            await update_progress(77, "Streaming export complete")
            
            # Background music is now added during FFmpeg streaming process with proper volume levels
            
            # Update progress - checking file size
            await update_progress(85, "Checking file size")
            
            # Video already created via streaming, now check size
            print(f"[VIDEO] ✅ Streaming export complete (Duration: {total_duration:.1f}s)...")
            
            # MEMORY CLEANUP: Clean up after streaming
            force_memory_cleanup()
            
            # Check if video file size is within limits 
            file_size = os.path.getsize(output_path)
            actual_limit_bytes = upload_limit_mb * 1024 * 1024
            
            if file_size > actual_limit_bytes:
                print(f"[VIDEO] 🆘 EMERGENCY compression needed ({file_size/1024/1024:.1f}MB > {upload_limit_mb}MB)")
                compressed_path = os.path.join(temp_dir, "emergency_compressed.mp4")
                
                # EMERGENCY COMPRESSION: 720p ultrafast with CRF for optimal quality/size
                emergency_audio = 64  # 64k audio
                print(f"[VIDEO] 🔥 EMERGENCY COMPRESSION: 720p ultrafast + {emergency_audio}k audio (CRF optimized)")
                
                def emergency_compress_sync():
                    """MEMORY-OPTIMIZED EMERGENCY ultra-compression using FFmpeg"""
                    import subprocess
                    import gc
                    
                    # Force memory cleanup before compression
                    gc.collect()
                    
                    memory_before_compress = get_memory_usage()
                    print(f"[MEMORY] 💾 Memory before compression: {memory_before_compress:.1f}MB")
                    
                    # Use FFmpeg to re-compress the existing video file with CRF optimization
                    compress_cmd = [
                        'ffmpeg', '-y',
                        '-i', output_path,  # Input the already created video
                        '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-crf', '28',  # Higher CRF for smaller size while maintaining quality
                        '-c:a', 'aac', '-b:a', f'{emergency_audio}k',
                        '-r', '24',  # Keep 24fps for smooth playback
                        '-movflags', '+faststart',
                        compressed_path
                    ]
                    
                    try:
                        subprocess.run(compress_cmd, capture_output=True, check=True)
                        print("[FFMPEG] ✅ Emergency compression complete")
                    except subprocess.CalledProcessError as e:
                        print(f"[FFMPEG] ❌ Emergency compression failed: {e}")
                        raise
                    
                    memory_after_compress = get_memory_usage()
                    print(f"[MEMORY] 💾 Memory after compression: {memory_after_compress:.1f}MB")
                
                import concurrent.futures
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    await loop.run_in_executor(executor, emergency_compress_sync)
                
                final_size = os.path.getsize(compressed_path)
                print(f"[VIDEO] ✅ EMERGENCY compressed to {final_size/1024/1024:.1f}MB")
                output_path = compressed_path
            else:
                print(f"[VIDEO] ✅ Size perfect ({file_size/1024/1024:.1f}MB)")
            
            # Yield after compression check
            await asyncio.sleep(0.1)
            
            # STREAMING: No video clips to close (memory already optimized)
            
            # Update progress - preparing for upload
            await update_progress(96, "Preparing for upload")
            
            # Read and return video
            with open(output_path, "rb") as f:
                video_data = f.read()
            
            print(f"[VIDEO] 🎉 STREAMING meme video completed! Total duration: {total_duration:.1f}s")
            
            # Add final completion message with server boost reminder
            if progress_msg:
                try:
                    completion_message = f"🎬 **Chat video complete!** ({total_duration:.1f}s)\n\n{server_info}"
                    await progress_msg.edit(content=completion_message)
                except Exception as e:
                    print(f"[PROGRESS] ⚠️ Failed to update final message: {e}")
            
            # FINAL MEMORY CLEANUP before returning video
            print("[MEMORY] 🧹 Final memory cleanup...")
            force_memory_cleanup()
            
            final_memory = get_memory_usage()
            print(f"[MEMORY] 💾 Final memory usage: {final_memory:.1f}MB")
            
            return io.BytesIO(video_data)
            
        except Exception as e:
            print(f"[VIDEO] ❌ Error combining clips: {e}")
            # Fallback: use the old method
            image_files = [os.path.join(temp_dir, f"frame_{i:03d}.png") for i in range(len(valid_messages))]
            fps = len(valid_messages) / duration
            return generate_video_from_images(image_files, fps=fps)

# Legacy function alias for backward compatibility
async def generate_meme_video_with_progress(messages: list, duration: float = 21.0, progress_msg=None, guild=None) -> io.BytesIO:
    """Wrapper function that calls the next-level generator with progress updates"""
    return await generate_meme_video_nextlevel(messages, duration, progress_msg, guild)

async def generate_meme_video(messages: list, duration: float = 21.0) -> io.BytesIO:
    """Legacy function that now calls the next-level implementation without progress updates"""
    return await generate_meme_video_nextlevel(messages, duration, None)

# Testing block (for local testing, replace with your Discord bot command handler)
if __name__ == '__main__':
    test_messages = [
        {"name": "PhoenixFan", "message": "I love this series?", "avatar": "https://example.com/avatar1.png"},
        {"name": "EdgeworthLover", "message": "This is incredible!", "avatar": "https://example.com/avatar2.png"},
        {"name": "PhoenixFan", "message": "objection! That can't be right.", "avatar": "https://example.com/avatar1.png"},
        {"name": "NewUser", "message": "Hold it, wait a minute...", "avatar": "https://example.com/avatar3.png"},
        {"name": "RandomUser", "message": "take that! You got served.", "avatar": "https://example.com/avatar4.png"}
    ]
    try:
        video_buf = asyncio.run(generate_meme_video(test_messages))
        with open("meme_video.mp4", "wb") as f:
            f.write(video_buf.getbuffer())
        print("Meme video rendered and saved to meme_video.mp4")
    except Exception as e:
        print(f"An error occurred: {e}")