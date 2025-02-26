import io
import os
import random
import asyncio
import logging
import tempfile
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

logging.basicConfig(level=logging.INFO)

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

def render_message_image(username: str, message: str, avatar_url: str = None, width: int = 640, 
                         height: int = 480, style: str = "modern", image_url: str = None) -> Image.Image:
    """
    Render an image for a chat message with enhanced visual styling.
    
    Args:
        username: The username to display
        message: The message text
        avatar_url: URL to the user's avatar image
        width: Image width
        height: Image height
        style: Visual style ("modern", "retro", "dark", "bubbly", "neon")
        image_url: URL to an attached image (if any)
    """
    # Style presets
    styles = {
        "modern": {
            "bg": (245, 245, 250),
            "username_color": (59, 89, 152),
            "text_color": (33, 33, 33),
            "accent": (66, 133, 244),
            "shadow": True
        },
        "retro": {
            "bg": (255, 248, 231),
            "username_color": (217, 72, 15),
            "text_color": (94, 65, 47),
            "accent": (217, 72, 15),
            "shadow": False
        },
        "dark": {
            "bg": (33, 33, 33),
            "username_color": (250, 250, 250),
            "text_color": (220, 220, 220),
            "accent": (86, 156, 214),
            "shadow": True
        },
        "bubbly": {
            "bg": (255, 255, 255),
            "username_color": (77, 144, 254),
            "text_color": (40, 40, 40),
            "accent": (77, 144, 254),
            "bubble": True
        },
        "neon": {
            "bg": (20, 20, 35),
            "username_color": (255, 41, 117),
            "text_color": (240, 240, 255),
            "accent": (41, 240, 255),
            "glow": True
        }
    }
    
    # Use the selected style or default to modern
    style_config = styles.get(style, styles["modern"])
    
    # Create the base image
    img = Image.new("RGB", (width, height), color=style_config["bg"])
    draw = ImageDraw.Draw(img)
    
    # Load fonts (fallback to default if not available)
    try:
        font_username = ImageFont.truetype("arialbd.ttf", 38)
        font_message = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font_username = ImageFont.load_default()
        font_message = ImageFont.load_default()
    
    # Initial positioning
    x_offset = 20
    y_offset = 20
    
    # If an avatar URL is provided, fetch and paste the avatar
    avatar_size = (100, 100)
    avatar_padding = 20
    if avatar_url:
        avatar_img = fetch_avatar(avatar_url, size=avatar_size)
        if avatar_img:
            if style_config.get("glow"):
                # Add glow effect to avatar for neon style
                glow = Image.new("RGBA", (avatar_size[0]+10, avatar_size[1]+10), (0, 0, 0, 0))
                glow_draw = ImageDraw.Draw(glow)
                glow_draw.ellipse((0, 0, avatar_size[0]+10, avatar_size[1]+10), 
                                 fill=style_config["accent"])
                img.paste(glow, (avatar_padding-5, avatar_padding-5), mask=glow)
                
            img.paste(avatar_img, (avatar_padding, avatar_padding), mask=avatar_img)
            x_offset += avatar_img.width + avatar_padding
    
    # Draw username with style
    if style_config.get("shadow") and not style_config.get("glow"):
        # Add shadow effect
        draw.text((x_offset+2, y_offset+2), username, fill=(0, 0, 0, 128), font=font_username)
    
    if style_config.get("glow"):
        # Add glow effect for neon style
        for offset in range(3, 0, -1):
            alpha = 90 - (offset * 30)
            draw.text((x_offset-offset, y_offset), username, 
                     fill=(*style_config["accent"], alpha), font=font_username)
            draw.text((x_offset+offset, y_offset), username, 
                     fill=(*style_config["accent"], alpha), font=font_username)
    
    draw.text((x_offset, y_offset), username, fill=style_config["username_color"], font=font_username)
    
    # Determine layout based on whether there's an image or not
    has_image = image_url is not None
    
    # Calculate starting y position for text content
    text_start_y = y_offset + 60
    text_width = width - x_offset - 20
    
    # Handle attached image if present
    if has_image:
        try:
            # Download and process attached image
            response = requests.get(image_url)
            response.raise_for_status()
            attached_img = Image.open(io.BytesIO(response.content))
            
            # Calculate image size to fit within the message area
            # Maximum dimensions while maintaining aspect ratio
            max_img_width = width - x_offset - 40
            max_img_height = 200  # Limit height to leave room for text
            
            # Calculate scaled dimensions
            img_width, img_height = attached_img.size
            scale = min(max_img_width/img_width, max_img_height/img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            # Resize the image
            attached_img = attached_img.resize((new_width, new_height), Image.LANCZOS)
            
            # Draw border around image based on style
            if style_config.get("bubble"):
                # Create a rounded rectangle background for the image
                img_bg = Image.new("RGBA", (new_width + 10, new_height + 10), (240, 240, 250, 255))
                img_mask = Image.new("L", (new_width + 10, new_height + 10), 0)
                img_mask_draw = ImageDraw.Draw(img_mask)
                img_mask_draw.rounded_rectangle((0, 0, new_width + 10, new_height + 10), radius=10, fill=255)
                
                # Paste the image onto the background
                img_bg.paste(attached_img, (5, 5))
                
                # Paste the result onto the main image
                img.paste(img_bg, (x_offset, text_start_y), mask=img_mask)
            else:
                # Simple border
                border_color = style_config["accent"]
                border_width = 3
                
                # Draw border
                border = Image.new("RGBA", (new_width + 2*border_width, new_height + 2*border_width), border_color)
                border.paste(attached_img, (border_width, border_width))
                
                # Paste onto main image
                img.paste(border, (x_offset, text_start_y))
            
            # Update text starting position to be below the image
            text_start_y += new_height + 20
            
        except Exception as e:
            logging.error(f"Error processing attached image: {e}")
            # If image processing fails, just continue with text
    
    # Create message bubble or render text directly
    if style_config.get("bubble"):
        # Calculate text size for bubble
        max_text_width = width - x_offset - 40
        words = message.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            w, _ = get_text_size(draw, test_line, font_message)
            if w <= max_text_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Calculate bubble height
        line_height = get_text_size(draw, "Tg", font_message)[1] + 5
        bubble_height = (len(lines) * line_height) + 30
        bubble_width = min(max(get_text_size(draw, line, font_message)[0] for line in lines) + 40, max_text_width)
        
        # Draw bubble
        bubble_x = x_offset
        bubble_y = text_start_y
        bubble_radius = 20
        
        # Draw rounded rectangle
        draw.rounded_rectangle(
            (bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height),
            radius=bubble_radius,
            fill=(240, 240, 250)
        )
        
        # Draw text inside bubble
        text_x = bubble_x + 20
        text_y = bubble_y + 15
        for line in lines:
            draw.text((text_x, text_y), line, fill=style_config["text_color"], font=font_message)
            text_y += line_height
    else:
        # Standard text rendering
        max_text_width = width - x_offset - 20
        words = message.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            w, _ = get_text_size(draw, test_line, font_message)
            if w <= max_text_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        y_text = text_start_y
        for line in lines:
            if style_config.get("shadow"):
                draw.text((x_offset+1, y_text+1), line, fill=(0, 0, 0, 128), font=font_message)
            
            if style_config.get("glow"):
                for offset in range(2, 0, -1):
                    alpha = 90 - (offset * 30)
                    draw.text((x_offset-offset, y_text), line, 
                             fill=(*style_config["accent"], alpha), font=font_message)
            
            draw.text((x_offset, y_text), line, fill=style_config["text_color"], font=font_message)
            y_text += get_text_size(draw, line, font_message)[1] + 5
    
    # Add finishing touches based on style
    if style == "retro":
        # Add a vintage filter
        overlay = Image.new("RGB", img.size, (250, 220, 180))
        img = Image.blend(img, overlay, 0.1)
    
    return img

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
            "-preset", "medium",  # Better quality
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

async def generate_meme_video(messages: list, duration: float = 22.0) -> io.BytesIO:
    """
    Generate a meme video from Discord messages.
    Creates one image per message, then uses FFmpeg to stitch them into a video (MP4).
    
    Args:
        messages (list): List of dicts with keys "name", "message", and "avatar".
        duration (float): Total duration of the video in seconds (default 22.0).
    
    Returns:
        io.BytesIO: Buffer containing the final video.
    """
    if not messages or not isinstance(messages, list):
        raise ValueError("No messages provided or messages is not a list.")
    
    # Calculate frames per second based on message count and desired duration
    message_count = len(messages)
    fps = message_count / duration
    
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        image_files = []
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict) or "name" not in msg or "message" not in msg:
                continue
            
            username = msg["name"]
            text = msg["message"]
            avatar_url = msg.get("avatar")
            image_url = msg.get("image_url") if msg.get("has_image") else None
            
            # Enhanced rendering with visual styles and image support
            img = render_message_image(
                username, 
                text, 
                avatar_url,
                style=random.choice(["modern", "retro", "dark", "bubbly", "neon"]),
                image_url=image_url
            )
            
            image_path = os.path.join(temp_dir, f"frame_{i:03d}.png")
            img.save(image_path)
            image_files.append(image_path)
        
        if not image_files:
            raise ValueError("No valid images were generated from messages.")
        
        # Pass the fps parameter to ensure correct duration
        video_buffer = generate_video_from_images(image_files, fps=fps)
        return video_buffer

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
