import discord
from discord import app_commands
import random, httpx, aiohttp
from engine.ai.gemini import slash_ai_response, slash_ai8b_response, mystery
from engine.utils import load_env, giphy_env, get_reddit_access_token
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()
# Your bot's token and Giphy API key
GIPHY_API_KEY = giphy_env()

# Define the roast command
@app_commands.command(name="roast", description="Roast a user in a light-hearted way!")
async def roast_command(interaction: discord.Interaction, user: discord.User):
    # Check if the bot is mentioned
    if user == interaction.client.user:
        await interaction.response.send_message("I can't roast myself! Try roasting someone else. 😅")
        return

    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()

    # Create a roast prompt specifically targeting the user
    roast_prompt = f"Roast {user.name} in a funny, light-hearted, and slang style. Make it playful and not too harsh."

    # Get the AI response for the roast
    response = await slash_ai_response(roast_prompt)
    
    # Send the roast as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="compliment", description="Compliment a user in a light-hearted way!")
async def compliment_command(interaction: discord.Interaction, user: discord.User):
    # Check if the bot is mentioned
    if user == interaction.client.user:
        await interaction.response.send_message("I can't compliment myself! Try complimenting someone else. 😅")
        return

    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()

    # Create a compliment prompt specifically targeting the user
    compliment_prompt = f"Compliment {user.name} in a friendly, light-hearted, and slang style. Make it positive and uplifting."

    # Get the AI response for the compliment
    response = await slash_ai_response(compliment_prompt)
    
    # Send the compliment as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="joke", description="Get a light-hearted joke from the bot!")
async def joke_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()

    # Create a joke prompt
    joke_prompt = "Tell a light-hearted, funny joke that will make the user laugh."

    # Get the AI response for the joke
    response = await slash_ai_response(joke_prompt)
    
    # Send the joke as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="fact", description="Get a random interesting fact from the bot!")
async def fact_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a fact prompt
    fact_prompt = "Tell a random, interesting fact that will surprise the user."
    
    # Get the AI response for the fact
    response = await slash_ai_response(fact_prompt)
    
    # Send the fact as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="quote", description="Get an inspiring quote from the bot!")
async def quote_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a quote prompt
    quote_prompt = "Share an inspiring, motivational quote that will uplift the user."
    
    # Get the AI response for the quote
    response = await slash_ai_response(quote_prompt)
    
    # Send the quote as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="advice", description="Get a piece of advice from the bot!")
async def advice_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create an advice prompt
    advice_prompt = "Give a piece of advice that will help the user in their daily life."
    
    # Get the AI response for the advice
    response = await slash_ai_response(advice_prompt)
    
    # Send the advice as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="riddle", description="Get a fun riddle from the bot!")
async def riddle_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a riddle prompt
    riddle_prompt = "Share a fun, challenging riddle that will make the user think."
    
    # Get the AI response for the riddle
    response = await slash_ai_response(riddle_prompt)
    
    # Send the riddle as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="horoscope", description="Get a horoscope prediction for your zodiac sign!")
async def horoscope_command(interaction: discord.Interaction, sign: str):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a horoscope prompt
    horoscope_prompt = f"Share a horoscope prediction for the {sign} zodiac sign."
    
    # Get the AI response for the horoscope
    response = await slash_ai8b_response(horoscope_prompt)
    
    # Send the horoscope prediction as a reply after deferring
    await interaction.followup.send(f"{response}")

@app_commands.command(name="rps", description="Play Rock, Paper, Scissors with the bot!")
async def rps_command(interaction: discord.Interaction, choice: str):
    await interaction.response.defer()  # Defer the interaction response

    response = random.choice(["rock", "paper", "scissors"])

    # Create an embed for the result
    embed = discord.Embed(title="Rock, Paper, Scissors")
    embed.add_field(name="Your Choice", value=choice.capitalize(), inline=True)
    embed.add_field(name="Bot's Choice", value=response.capitalize(), inline=True)

    # Determine the result
    if choice == response:
        result = "It's a tie!"
        color = discord.Color.gold()
    elif (choice == "rock" and response == "scissors") or (choice == "scissors" and response == "paper") or (choice == "paper" and response == "rock"):
        result = "You win!"
        color = discord.Color.green()
    else:
        result = "You lose!"
        color = discord.Color.red()

    embed.color = color
    embed.add_field(name="Result", value=result, inline=False)

    # Send the final response
    await interaction.followup.send(embed=embed)
    
@app_commands.command(name="coinflip", description="Flip a coin and see the result!")
async def coinflip_command(interaction: discord.Interaction):
    response = random.choice(["Heads", "Tails"])

    # Create an embed for the result
    embed = discord.Embed(title="Coin Flip")
    embed.add_field(name="Result", value=response, inline=True)

    # Send the embed as a reply after deferring
    await interaction.response.send_message(embed=embed)
    
@app_commands.command(name="dice", description="Roll a dice and see the result!")
async def dice_command(interaction: discord.Interaction):
    response = random.randint(1, 6)

    # Create an embed for the result
    embed = discord.Embed(title="Dice Roll")
    embed.add_field(name="Result", value=response, inline=True)

    # Send the embed as a reply after deferring
    await interaction.response.send_message(embed=embed)
    
@app_commands.command(name="magic8ball", description="Ask the Magic 8-Ball a question!")
async def magic8ball_command(interaction: discord.Interaction, question: str):
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes - definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]
    response = random.choice(responses)

    # Send the Magic 8-Ball response as a reply
    await interaction.response.send_message(f"🎱 {response}")
    
@app_commands.command(name="choose", description="Let the bot choose between multiple options!")
async def choose_command(interaction: discord.Interaction, options: str):
    # Split the options by commas
    option_list = [option.strip() for option in options.split(",")]

    # Choose a random option
    response = random.choice(option_list)

    # Send the chosen option as a reply
    await interaction.response.send_message(f"I choose: {response}")
    
@app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with the bot!")
async def tictactoe_command(interaction: discord.Interaction):
    # Create a Tic-Tac-Toe board
    board = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

    # Send the Tic-Tac-Toe board as a reply
    await interaction.response.send_message(f"```\n{board[0]} | {board[1]} | {board[2]}\n---------\n{board[3]} | {board[4]} | {board[5]}\n---------\n{board[6]} | {board[7]} | {board[8]}\n```")
    
@app_commands.command(name="trivia", description="Play a fun trivia quiz with the bot!")
async def trivia_command(interaction: discord.Interaction):
    # Create a list of trivia questions and answers
    trivia = {
        "What is the capital of France?": "Paris",
        "What is the largest planet in our solar system?": "Jupiter",
        "Who painted the Mona Lisa?": "Leonardo da Vinci",
        "What is the tallest mountain in the world?": "Mount Everest",
        "What is the currency of Japan?": "Yen",
        "Who wrote Romeo and Juliet?": "William Shakespeare",
        "What is the chemical symbol for gold?": "Au",
        "What is the largest ocean on Earth?": "Pacific Ocean",
        "Who is known as the father of modern physics?": "Isaac Newton",
        "What is the largest mammal in the world?": "Blue Whale"
    }
    
    # Choose a random question from the trivia list
    question = random.choice(list(trivia.keys()))
    
    # Send the trivia question as a reply
    await interaction.response.send_message(f"**Trivia Question:** {question}")

@app_commands.command(name="rpsls", description="Play Rock, Paper, Scissors, Lizard, Spock with the bot!")
async def rpsls_command(interaction: discord.Interaction, choice: str):
    await interaction.response.defer()  # Defer the interaction response

    response = random.choice(["rock", "paper", "scissors", "lizard", "spock"])

    # Create an embed for the result
    embed = discord.Embed(title="Rock, Paper, Scissors, Lizard, Spock")
    embed.add_field(name="Your Choice", value=choice.capitalize(), inline=True)
    embed.add_field(name="Bot's Choice", value=response.capitalize(), inline=True)

    # Determine the result
    if choice == response:
        result = "It's a tie!"
        color = discord.Color.gold()
    elif (choice == "rock" and (response == "scissors" or response == "lizard")) or (choice == "paper" and (response == "rock" or response == "spock")) or (choice == "scissors" and (response == "paper" or response == "lizard")) or (choice == "lizard" and (response == "spock" or response == "paper")) or (choice == "spock" and (response == "rock" or response == "scissors")):
        result = "You win!"
        color = discord.Color.green()
    else:
        result = "You lose!"
        color = discord.Color.red()

    embed.color = color
    embed.add_field(name="Result", value=result, inline=False)

    # Send the final response
    await interaction.followup.send(embed=embed)
    
@app_commands.command(name="wordle", description="Play a fun word puzzle game with the bot!")
async def wordle_command(interaction: discord.Interaction):
    # Create a list of words for the game
    words = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon"]
    
    # Choose a random word from the list
    word = random.choice(words)
    
    # Create a hidden word with underscores
    hidden_word = "_" * len(word)
    
    # Send the hidden word as a reply
    await interaction.response.send_message(f"```\n{hidden_word}\n```")
    
# Meme command
@app_commands.command(name="meme", description="Get a random meme from r/memes.")
async def meme_command(interaction: discord.Interaction):
    await interaction.response.defer()

    access_token = await get_reddit_access_token()
    url = "https://oauth.reddit.com/r/memes/hot.json?limit=50"  # Note the OAuth URL
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "seeyuh/0.1.0 (by u/drgamerarko)"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Extract memes from the response
        memes = data["data"]["children"]
        random_meme = random.choice(memes)["data"]

        # Create and send the embed with the meme
        embed = discord.Embed(title=random_meme["title"], color=discord.Color.random())
        embed.set_image(url=random_meme["url"])
        embed.set_footer(text=f"👍 {random_meme['score']} | 💬 {random_meme['num_comments']} comments", icon_url=interaction.client.user.avatar.url)

        await interaction.followup.send(embed=embed)

    except httpx.HTTPStatusError as e:
        await interaction.followup.send("There was an error fetching memes from Reddit. Please try again later.")
        print(f"HTTP error: {e}")
    except Exception as e:
        await interaction.followup.send("An unexpected error occurred. Please try again later.")
        print(f"Unexpected error: {e}")
               
# Define the /gif slash command
@app_commands.command(name="gif", description="Search for a GIF on Giphy.")
async def gif_command(interaction: discord.Interaction, query: str):
    # Asynchronously fetch a GIF from Giphy
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.giphy.com/v1/gifs/search",
            params={"api_key": GIPHY_API_KEY, "q": query, "limit": 1}
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data["data"]:
                    gif_url = data["data"][0]["images"]["original"]["url"]
                    await interaction.response.send_message(gif_url)
                else:
                    await interaction.response.send_message("No GIFs found for your query.")
            else:
                await interaction.response.send_message("Error fetching GIF. Try again later.")

@app_commands.command(name="seeyuh", description="Learn what seeyuh truly feels. 😔")
async def mystery_command(interaction: discord.Interaction):
    await interaction.response.defer()  # Defer the interaction response
    response = await mystery("Give a mysterious, cryptic response that will intrigue the user.")
    await interaction.followup.send(response)  # Use followup.send instead of response.send_message
