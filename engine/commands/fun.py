import discord, random, httpx, aiohttp, asyncio, urllib.parse, io, aiofiles, time, logging, os, tempfile
from discord import app_commands
from difflib import get_close_matches
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from engine.ai.gemini import slash_ai_response, slash_ai8b_response, mystery
from engine.utils import load_env, giphy_env, get_reddit_access_token, imgflip_env, hf_env
from html import unescape
from bs4 import BeautifulSoup
from urllib.parse import quote
from contextlib import contextmanager
from pathlib import Path

logging.basicConfig(level=logging.INFO)

DISCORD_TOKEN, OWNER, url, key = load_env()
GIPHY_API_KEY = giphy_env()

@contextmanager
def safe_tempfile(guild_id: int):
    """Create a temporary file that gets cleaned up after use"""
    temp_dir = Path("./temp")
    temp_dir.mkdir(exist_ok=True)
    
    temp_path = temp_dir / f"sound_{guild_id}_{int(time.time())}.mp3"
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            temp_path.unlink()
            
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
    await interaction.response.defer()

    url = "https://official-joke-api.appspot.com/jokes/random"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            joke_data = response.json()
            setup = joke_data["setup"]
            punchline = joke_data["punchline"]
            joke = f"{setup}\n\n{punchline}"
    except httpx.HTTPStatusError as e:
        joke = "There was an error fetching a joke. Please try again later."
        print(f"HTTP error: {e}")
    except Exception as e:
        joke = "An unexpected error occurred. Please try again later."
        print(f"Unexpected error: {e}")

    await interaction.followup.send(joke)
    
@app_commands.command(name="fact", description="Get a random interesting fact from the bot!")
async def fact_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a fact prompt
    fact_prompt = "Tell a random, interesting fact that will surprise the user."
    
    # Get the AI response for the fact
    response = await slash_ai8b_response(fact_prompt)
    
    # Send the fact as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="quote", description="Get an inspiring quote from the bot!")
async def quote_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a quote prompt
    quote_prompt = "Share an inspiring, motivational quote that will uplift the user."
    
    # Get the AI response for the quote
    response = await slash_ai8b_response(quote_prompt)
    
    # Send the quote as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="advice", description="Get a piece of advice from the bot!")
async def advice_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create an advice prompt
    advice_prompt = "Give a piece of advice that will help the user in their daily life."
    
    # Get the AI response for the advice
    response = await slash_ai8b_response(advice_prompt)
    
    # Send the advice as a reply after deferring
    await interaction.followup.send(f"{response}")
    
@app_commands.command(name="riddle", description="Get a fun riddle from the bot!")
async def riddle_command(interaction: discord.Interaction):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a riddle prompt
    riddle_prompt = "Share a fun, challenging riddle that will make the user think and solve."
    
    # Get the AI response for the riddle
    response = await slash_ai8b_response(riddle_prompt)
    
    # Send the riddle as a reply after deferring
    await interaction.followup.send(f"{response}")
    
# Define the zodiac signs with emojis
zodiac_signs = [
    app_commands.Choice(name="Aries ♈", value="Aries"),
    app_commands.Choice(name="Taurus ♉", value="Taurus"),
    app_commands.Choice(name="Gemini ♊", value="Gemini"),
    app_commands.Choice(name="Cancer ♋", value="Cancer"),
    app_commands.Choice(name="Leo ♌", value="Leo"),
    app_commands.Choice(name="Virgo ♍", value="Virgo"),
    app_commands.Choice(name="Libra ♎", value="Libra"),
    app_commands.Choice(name="Scorpio ♏", value="Scorpio"),
    app_commands.Choice(name="Sagittarius ♐", value="Sagittarius"),
    app_commands.Choice(name="Capricorn ♑", value="Capricorn"),
    app_commands.Choice(name="Aquarius ♒", value="Aquarius"),
    app_commands.Choice(name="Pisces ♓", value="Pisces")
]

# Define the emojis for each zodiac sign
zodiac_emojis = {
    "Aries": "♈",
    "Taurus": "♉",
    "Gemini": "♊",
    "Cancer": "♋",
    "Leo": "♌",
    "Virgo": "♍",
    "Libra": "♎",
    "Scorpio": "♏",
    "Sagittarius": "♐",
    "Capricorn": "♑",
    "Aquarius": "♒",
    "Pisces": "♓"
}

@app_commands.command(name="horoscope", description="Get a horoscope prediction for your zodiac sign!")
@app_commands.choices(sign=zodiac_signs)
async def horoscope_command(interaction: discord.Interaction, sign: app_commands.Choice[str]):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()
    
    # Create a horoscope prompt
    horoscope_prompt = f"Share a horoscope prediction for the {sign.value} zodiac sign."
    
    # Get the AI response for the horoscope
    response = await slash_ai8b_response(horoscope_prompt)
    
    # Create an embed for the horoscope prediction
    embed = discord.Embed(title=f"{sign.name} Horoscope", description=response, color=discord.Color.blue())
    embed.set_thumbnail(url=f"https://twemoji.maxcdn.com/v/latest/72x72/{ord(zodiac_emojis[sign.value]):x}.png")
    embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)
    
    # Send the horoscope prediction as a reply after deferring
    await interaction.followup.send(embed=embed)

# Define the choices with emojis
rps_choices = [
    app_commands.Choice(name="Rock 🪨", value="rock"),
    app_commands.Choice(name="Paper 📄", value="paper"),
    app_commands.Choice(name="Scissors ✂️", value="scissors")
]

# Define the emojis for each choice
rps_emojis = {
    "rock": "🪨",
    "paper": "📄",
    "scissors": "✂️"
}

@app_commands.command(name="rps", description="Play Rock, Paper, Scissors with the bot!")
@app_commands.describe(choice="Your choice of Rock, Paper, or Scissors")
@app_commands.choices(choice=rps_choices)
async def rps_command(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    await interaction.response.defer()  # Defer the interaction response

    response = random.choice(["rock", "paper", "scissors"])

    # Create an embed for the result
    embed = discord.Embed(title="Rock, Paper, Scissors")
    embed.add_field(name="Your Choice", value=f"{choice.name} {rps_emojis[choice.value]}", inline=True)
    embed.add_field(name="Bot's Choice", value=f"{response.capitalize()} {rps_emojis[response]}", inline=True)

    # Determine the result
    if choice.value == response:
        result = "It's a tie!"
        color = discord.Color.gold()
        thumbnail_emoji = rps_emojis[choice.value]
    elif (choice.value == "rock" and response == "scissors") or (choice.value == "scissors" and response == "paper") or (choice.value == "paper" and response == "rock"):
        result = "You win!"
        color = discord.Color.green()
        thumbnail_emoji = rps_emojis[choice.value]
    else:
        result = "You lose!"
        color = discord.Color.red()
        thumbnail_emoji = rps_emojis[response]

    embed.color = color
    embed.add_field(name="Result", value=result, inline=False)
    embed.set_thumbnail(url=f"https://twemoji.maxcdn.com/v/latest/72x72/{ord(thumbnail_emoji[0]):x}.png")
    embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)

    # Send the final response
    await interaction.followup.send(embed=embed)
    
@app_commands.command(name="coinflip", description="Flip a coin and see the result!")
async def coinflip_command(interaction: discord.Interaction):
    response = random.choice(["Heads", "Tails"])

    # Define the emojis for each result
    coin_emojis = {
        "Heads": "🪙",
        "Tails": "🔄"
    }

    # Create an embed for the result
    embed = discord.Embed(title="Coin Flip", color=discord.Color.blue())
    embed.add_field(name="Result", value=f"{response} {coin_emojis[response]}", inline=True)
    embed.set_thumbnail(url=f"https://twemoji.maxcdn.com/v/latest/72x72/{ord(coin_emojis[response]):x}.png")
    embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)

    # Send the embed as a reply after deferring
    await interaction.response.send_message(embed=embed)
    
@app_commands.command(name="dice", description="Roll a dice and see the result!")
async def dice_command(interaction: discord.Interaction):
    response = random.randint(1, 6)

    # Define the emojis for each dice face
    dice_emojis = {
        1: "⚀",
        2: "⚁",
        3: "⚂",
        4: "⚃",
        5: "⚄",
        6: "⚅"
    }

    # Create an embed for the result
    embed = discord.Embed(title="Dice Roll", color=discord.Color.blue())
    embed.add_field(name="Result", value=f"{response} {dice_emojis[response]}", inline=True)
    embed.set_thumbnail(url=f"https://twemoji.maxcdn.com/v/latest/72x72/{ord(dice_emojis[response]):x}.png")
    embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)

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
    await interaction.response.send_message(f"\n> {question} \n🎱 {response}")
    
@app_commands.command(name="choose", description="Let the bot choose between multiple options!")
async def choose_command(interaction: discord.Interaction, options: str):
    # Split the options by commas
    option_list = [option.strip() for option in options.split(",")]

    # Choose a random option
    response = random.choice(option_list)

    # Send the chosen option as a reply
    await interaction.response.send_message(f"> Choices: {options}\nI choose: {response}")
    
class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if view.current_player == "X":
            self.style = discord.ButtonStyle.danger
            self.label = "X"
            view.board[self.y][self.x] = "X"
            view.current_player = "O"
        else:
            self.style = discord.ButtonStyle.success
            self.label = "O"
            view.board[self.y][self.x] = "O"
            view.current_player = "X"

        self.disabled = True
        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            view.stop()
            await interaction.response.edit_message(content=f"{winner} wins!", view=view)
        elif view.is_board_full():
            for child in view.children:
                child.disabled = True
            view.stop()
            await interaction.response.edit_message(content="It's a tie!", view=view)
        else:
            await interaction.response.edit_message(content=f"{view.current_player}'s turn", view=view)

class TicTacToeView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.current_player = "X"
        self.board = [["" for _ in range(3)] for _ in range(3)]
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] != "":
                return row[0]
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != "":
                return self.board[0][col]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != "":
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != "":
            return self.board[0][2]
        return None

    def is_board_full(self):
        return all(cell != "" for row in self.board for cell in row)

@app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with the bot!")
async def tictactoe_command(interaction: discord.Interaction):
    view = TicTacToeView()
    await interaction.response.send_message("X's turn", view=view)

@app_commands.command(name="trivia", description="Play a fun trivia quiz with the bot!")
async def trivia_command(interaction: discord.Interaction):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://opentdb.com/api.php?amount=1&type=multiple') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['response_code'] == 0:
                        question_data = data['results'][0]
                        # Decode HTML entities in the question and answers
                        question = unescape(question_data['question'])
                        correct_answer = unescape(question_data['correct_answer'])
                        incorrect_answers = [unescape(ans) for ans in question_data['incorrect_answers']]
                        all_answers = incorrect_answers + [correct_answer]
                        random.shuffle(all_answers)
                    else:
                        raise ValueError("No trivia questions available.")
                else:
                    raise ConnectionError("Failed to fetch trivia question.")
    except Exception as e:
        # Use the fallback trivia dictionary (same as before)
        # ... [previous trivia dictionary remains unchanged]
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
        "What is the largest mammal in the world?": "Blue Whale",
        "What is the smallest country in the world?": "Vatican City",
        "Who is the author of the Harry Potter book series?": "J.K. Rowling",
        "What is the national animal of Australia?": "Kangaroo",
        "What is the main ingredient in guacamole?": "Avocado",
        "What is the largest desert in the world?": "Antarctica",
        "Who discovered penicillin?": "Alexander Fleming",
        "What is the national flower of Japan?": "Cherry Blossom",
        "What is the largest species of shark?": "Whale Shark",
        "Who painted the ceiling of the Sistine Chapel?": "Michelangelo",
        "What is the largest bird in the world?": "Ostrich",
        "What is the national sport of Canada?": "Ice Hockey",
        "Who is the lead singer of the band Queen?": "Freddie Mercury",
        "What is the national dish of Spain?": "Paella",
        "What is the largest lake in Africa?": "Lake Victoria",
        "Who wrote the novel Moby-D?": "Herman Melville",
        "What is the national animal of China?": "Giant Panda",
        "What is the largest island in the world?": "Greenland",
        "Who is the Greek god of the sea?": "Poseidon",
        "What is the national flower of India?": "Lotus",
        "What is the national tree of the United States?": "Oak",
        "Who is known as the father of modern psychology?": "Sigmund Freud",
        "What is the national sport of Japan?": "Sumo Wrestling",
        "Who wrote the play Hamlet?": "William Shakespeare",
        "What is the national bird of the United States?": "Bald Eagle",
        "What is the national instrument of Scotland?": "Bagpipes",
        "Who is the author of the novel 1984?": "George Orwell",
        "What is the national animal of Australia?": "Kangaroo",
        "What is the national flower of France?": "Lily",
        "Who painted the Starry Night?": "Vincent van Gogh",
        "What is the national dish of Italy?": "Pizza",
        "What is the national animal of Russia?": "Brown Bear",
        "Who is known as the father of modern chemistry?": "Antoine Lavoisier",
        "What is the national sport of Brazil?": "Football",
        "Who wrote the play Macbeth?": "William Shakespeare",
        "What is the national bird of India?": "Indian Peafowl",
        "What is the national instrument of Japan?": "Shamisen",
        "Who is the author of the novel Pride and Prejudice?": "Jane Austen",
        "What is the national animal of Canada?": "Beaver",
        "What is the national flower of Australia?": "Golden Wattle",
        "Who painted the Last Supper?": "Leonardo da Vinci",
        "What is the national dish of China?": "Peking Duck",
        "Who is known as the father of modern biology?": "Charles Darwin",
        "What is the national sport of Australia?": "Cricket",
        "Who wrote the play Othello?": "William Shakespeare",
        "What is the national bird of Canada?": "Common Loon",
        "What is the national instrument of Spain?": "Guitar",
        "Who is the author of the novel Jane Eyre?": "Charlotte Bronte",
        "What is the national flower of China?": "Peony",
        "Who painted the Birth of Venus?": "Sandro Botticelli",
        "What is the national dish of Japan?": "Sushi",
        "Who is known as the father of modern mathematics?": "Leonhard Euler",
        "What is the national sport of England?": "Cricket",
        "Who wrote the play King Lear?": "William Shakespeare",
        "What is the national bird of Australia?": "Emu",
        "What is the national flower of England?": "Rose",
        "Who painted the Creation of Adam?": "Michelangelo",
        "What is the national dish of Italy?": "Pasta",
        "What is the national animal of India?": "Bengal Tiger",
        "Who is known as the father of modern philosophy?": "René Descartes",
        "What is the national sport of France?": "Football"
        }
        question, correct_answer = random.choice(list(trivia.items()))
        all_answers = [correct_answer]
        random.shuffle(all_answers)

    # Create buttons for answers
    class TriviaView(discord.ui.View):
        def __init__(self, answers, correct):
            super().__init__(timeout=30)
            self.correct = correct
            for idx, answer in enumerate(answers):
                self.add_item(TriviaButton(answer, idx))

    class TriviaButton(discord.ui.Button):
        def __init__(self, answer, idx):
            super().__init__(style=discord.ButtonStyle.primary, label=answer, custom_id=str(idx))

        async def callback(self, interaction: discord.Interaction):
            if self.label == self.view.correct:
                await interaction.response.send_message("Correct! 🎉")
            else:
                await interaction.response.send_message(f"Wrong! The correct answer was: {self.view.correct}")
            self.view.stop()

    # Create and send the view with buttons
    view = TriviaView(all_answers, correct_answer)
    embed = discord.Embed(title="Trivia Question", description=question, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view)

    # Handle timeout
    await view.wait()
    if not view.is_finished():
        await interaction.followup.send(f"Time's up! The correct answer was: {correct_answer}")

# Define the choices with emojis
rpsls_choices = [
    app_commands.Choice(name="Rock 🪨", value="rock"),
    app_commands.Choice(name="Paper 📄", value="paper"),
    app_commands.Choice(name="Scissors ✂️", value="scissors"),
    app_commands.Choice(name="Lizard 🦎", value="lizard"),
    app_commands.Choice(name="Spock 🖖", value="spock")
]

# Define the emojis for each choice
rpsls_emojis = {
    "rock": "🪨",
    "paper": "📄",
    "scissors": "✂️",
    "lizard": "🦎",
    "spock": "🖖"
}

@app_commands.command(name="rpsls", description="Play Rock, Paper, Scissors, Lizard, Spock with the bot!")
@app_commands.describe(choice="Your choice of Rock, Paper, Scissors, Lizard, or Spock")
@app_commands.choices(choice=rpsls_choices)
async def rpsls_command(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    await interaction.response.defer()  # Defer the interaction response

    response = random.choice(["rock", "paper", "scissors", "lizard", "spock"])

    # Create an embed for the result
    embed = discord.Embed(title="Rock, Paper, Scissors, Lizard, Spock")
    embed.add_field(name="Your Choice", value=f"{choice.name} {rpsls_emojis[choice.value]}", inline=True)
    embed.add_field(name="Bot's Choice", value=f"{response.capitalize()} {rpsls_emojis[response]}", inline=True)

    # Determine the result
    if choice.value == response:
        result = "It's a tie!"
        color = discord.Color.gold()
        thumbnail_emoji = rpsls_emojis[choice.value]
    elif (choice.value == "rock" and (response == "scissors" or response == "lizard")) or (choice.value == "paper" and (response == "rock" or response == "spock")) or (choice.value == "scissors" and (response == "paper" or response == "lizard")) or (choice.value == "lizard" and (response == "spock" or response == "paper")) or (choice.value == "spock" and (response == "rock" or response == "scissors")):
        result = "You win!"
        color = discord.Color.green()
        thumbnail_emoji = rpsls_emojis[choice.value]
    else:
        result = "You lose!"
        color = discord.Color.red()
        thumbnail_emoji = rpsls_emojis[response]

    embed.color = color
    embed.add_field(name="Result", value=result, inline=False)
    embed.set_thumbnail(url=f"https://twemoji.maxcdn.com/v/latest/72x72/{ord(thumbnail_emoji):x}.png")
    embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)

    # Send the final response
    await interaction.followup.send(embed=embed)
    
# Define the list of words for the game
words = [
    "apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon",
    "mango", "nectarine", "orange", "papaya", "quince", "raspberry", "strawberry", "tangerine", "ugli", "vanilla",
    "watermelon", "xigua", "yam", "zucchini"
]

@app_commands.command(name="wordle", description="Play a fun word puzzle game with the bot!")
async def wordle_command(interaction: discord.Interaction):
    # Choose a random word from the list
    word = random.choice(words)
    
    # Create a hidden word with underscores
    hidden_word = ["_" for _ in word]
    
    # Send the initial hidden word as a reply
    await interaction.response.send_message(f"```\n{' '.join(hidden_word)}\n```")

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    attempts = 6
    guessed_letters = set()

    while attempts > 0 and "_" in hidden_word:
        try:
            # Wait for the user's guess
            guess_message = await interaction.client.wait_for('message', check=check, timeout=30.0)
            guess = guess_message.content.strip().lower()

            if len(guess) != 1 or not guess.isalpha():
                await interaction.followup.send("Please guess a single letter.")
                continue

            if guess in guessed_letters:
                await interaction.followup.send("You already guessed that letter. Try a different one.")
                continue

            guessed_letters.add(guess)

            if guess in word:
                for i, letter in enumerate(word):
                    if letter == guess:
                        hidden_word[i] = guess
                await interaction.followup.send(f"Correct! The letter '{guess}' is in the word.")
            else:
                attempts -= 1
                await interaction.followup.send(f"Incorrect! The letter '{guess}' is not in the word. Attempts left: {attempts}")

            await interaction.followup.send(f"```\n{' '.join(hidden_word)}\n```")

        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to respond! Game over.")
            return

    if "_" not in hidden_word:
        await interaction.followup.send(f"Congratulations! You guessed the word: {word}")
    else:
        await interaction.followup.send(f"Game over! The word was: {word}")
    
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
        
@app_commands.command(name="dadjoke", description="Get a random dad joke!")
async def dadjoke_command(interaction: discord.Interaction, search: str = None):
    await interaction.response.defer()
    
    headers = {
        'Accept': 'application/json',
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Use base URL if no search term
            url = 'https://icanhazdadjoke.com/'
            if search:
                url += '/search'
                params = {'term': search, 'limit': 1}
                response = await client.get(url, headers=headers, params=params)
                data = response.json()
                if not data['results']:
                    await interaction.followup.send("No dad jokes found with that search term! Try another one.")
                    return
                joke = data['results'][0]['joke']
            else:
                response = await client.get(url, headers=headers)
                data = response.json()
                joke = data['joke']
                
        # Create and send the embed with the dad joke
        embed = discord.Embed(
            title="Dad Joke", 
            description=joke, 
            color=discord.Color.random()
        )
        embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        await interaction.followup.send("Failed to fetch a dad joke. Please try again later.")
        print(f"Error fetching dad joke: {e}")
        
COW_TYPES = {
    "default": """
    \\   ^__^
    \\  (oo)\\_______
    | (__ )\\       )\\/\\
    |    ||----w |
    |    ||     ||""",
    
    "dead": """
    \\   ^__^
    \\  (xx)\\_______
    | (__ )\\       )\\/\\
    |    ||----w |
    |    ||     ||""",
    
    "happy": """
    \\   ^__^
    \\  (^^)\\_______
    | (__ )\\       )\\/\\
    |    ||----w |
    |    ||     ||""",
    
    "sleepy": """
    \\   ^__^
    \\  (--)\\_______ 
    | (__ )\\       )\\/\\
    |    ||----w |
    |    ||     ||"""
}

@app_commands.command(name="cowsay", description="Get a custom cow to say something!")
@app_commands.choices(cow_type=[
    app_commands.Choice(name="Default", value="default"),
    app_commands.Choice(name="Dead", value="dead"),
    app_commands.Choice(name="Happy", value="happy"),
    app_commands.Choice(name="Sleepy", value="sleepy")
])
async def cowsay_command(interaction: discord.Interaction, message: str, cow_type: app_commands.Choice[str] = None):
    await interaction.response.defer()
    
    # Use default cow if no type specified
    cow_art = COW_TYPES[cow_type.value if cow_type else "default"]
    
    # Calculate message box width
    max_width = 40
    message_lines = [message[i:i+max_width] for i in range(0, len(message), max_width)]
    
    # Create message box
    width = max(len(line) for line in message_lines)
    box = ["     " + "_" * (width + 2)]
    if len(message_lines) == 1:
        box.append(f"    < {message_lines[0]} >")
    else:
        box.append(f"    / {message_lines[0]:<{width}} \\")
        for line in message_lines[1:-1]:
            box.append(f"    | {line:<{width}} |")
        box.append(f"    \\ {message_lines[-1]:<{width}} /")
    box.append("     " + "-" * (width + 2))
    
    # Combine message box with cow art
    final_message = "\n".join(box) + cow_art
    
    await interaction.followup.send(f"```{final_message}```")
    
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

async def download_image(url: str) -> Image.Image:
    """Download image from URL and return PIL Image object"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                image_data = await response.read()
                return Image.open(io.BytesIO(image_data))
            raise Exception(f"Failed to download image: {response.status}")

def add_text_to_image(image: Image.Image, top_text: str, bottom_text: str) -> Image.Image:
    """Add single-line top and bottom text to image in meme style"""
    # Convert image to RGB mode if needed
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGB')
        
    # Create drawing context
    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    # Calculate initial font size based on image dimensions
    font_size = int(min(width, height) / 8)  # Start with 1/8th of smallest dimension
    margin = int(height * 0.05)  # 5% margin
    
    try:
        font = ImageFont.truetype("assets/fonts/impact.ttf", font_size)
    except:
        font = ImageFont.load_default()
        
    # Adjust font size until text fits width with margin
    top_text = top_text.upper()
    bottom_text = bottom_text.upper()
    
    def get_fitting_font_size(text: str, max_width: int) -> ImageFont.FreeTypeFont:
        size = font_size
        test_font = font
        while draw.textlength(text, font=test_font) > (max_width - 2*margin):
            size = int(size * 0.9)  # Reduce by 10%
            try:
                test_font = ImageFont.truetype("assets/fonts/impact.ttf", size)
            except:
                test_font = ImageFont.load_default()
        return test_font
    
    # Get font sizes that fit for both texts
    top_font = get_fitting_font_size(top_text, width)
    bottom_font = get_fitting_font_size(bottom_text, width)
    
    # Use smaller of the two fonts for consistency
    final_font = top_font if top_font.size <= bottom_font.size else bottom_font
    
    # Draw top text
    text_width = draw.textlength(top_text, font=final_font)
    x = (width - text_width) / 2
    y = margin
    
    # Draw outline
    outline_width = max(2, int(final_font.size * 0.05))  # Scale outline with font
    for adj in range(-outline_width, outline_width + 1):
        for adj2 in range(-outline_width, outline_width + 1):
            draw.text((x+adj, y+adj2), top_text, font=final_font, fill='black')
    draw.text((x, y), top_text, font=final_font, fill='white')
    
    # Draw bottom text
    text_width = draw.textlength(bottom_text, font=final_font)
    x = (width - text_width) / 2
    y = height - margin - final_font.size
    
    # Draw outline
    for adj in range(-outline_width, outline_width + 1):
        for adj2 in range(-outline_width, outline_width + 1):
            draw.text((x+adj, y+adj2), bottom_text, font=final_font, fill='black')
    draw.text((x, y), bottom_text, font=final_font, fill='white')
    
    return image
    
# Load all meme templates from file
with open('engine/meme-templates.txt', 'r') as f:
    MEME_TEMPLATES = [line.strip() for line in f if line.strip()]

# Manually map common keywords to specific templates
MANUAL_TEMPLATE_MAP = {
    "drake": ["Drake Bad Good"],
    "10 guy": ["10 Guy"],
    "grumpy cat": ["Grumpy Cat"],
    "y u no": ["Y U No"],
    "futurama fry": ["Futurama Fry"],
    "chemistry cat": ["Chemistry Cat"],
    "condescending wonka": ["Condescending Wonka"]
}

def is_valid_image_url(url: str) -> bool:
    """Check if URL is a valid image URL"""
    return any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])

def clean_discord_url(url: str) -> str:
    """Clean Discord CDN URLs by removing query parameters"""
    base_url = url.split('?')[0]
    base_url = base_url.split('&format')[0]
    base_url = base_url.split('&width')[0]
    return base_url

def clean_template_name(name: str) -> str:
    """Convert template name to API format"""
    return name.replace(" ", "-")

def find_template(user_input: str, templates: list) -> Optional[str]:
    """Find closest matching template using manual and fuzzy matching"""
    user_input = user_input.lower()
    
    # Check manual map first
    for keyword, template_list in MANUAL_TEMPLATE_MAP.items():
        if keyword in user_input:
            return template_list[0]
    
    # Create map of lowercase names to original names
    template_map = {t.lower(): t for t in templates}
    
    # Direct match
    if user_input in template_map:
        return template_map[user_input]
    
    # Check if user input contains any part of the template names
    for template in template_map.keys():
        if user_input in template:
            return template_map[template]
    
    # Fuzzy match with a higher cutoff value
    matches = get_close_matches(user_input, template_map.keys(), n=1, cutoff=0.8)
    if matches:
        return template_map[matches[0]]
    
    return None

async def find_imgflip_template(session, template_name):
    """Find matching template on Imgflip"""
    async with session.get('https://api.imgflip.com/get_memes') as resp:
        data = await resp.json()
        if not data['success']:
            return None
            
        memes = data['data']['memes']
        # Clean template name for matching
        clean_search = template_name.lower().replace('-', ' ')
        
        # Try direct match first
        for meme in memes:
            if clean_search in meme['name'].lower():
                return meme
                
        # Fallback to fuzzy match
        matches = get_close_matches(clean_search, 
                                  [m['name'].lower() for m in memes],
                                  n=1, cutoff=0.6)
        if matches:
            for meme in memes:
                if meme['name'].lower() == matches[0]:
                    return meme
    return None

IMGFLIP_USERNAME, IMGFLIP_PASSWORD = imgflip_env()

@app_commands.command(
    name="memegen",
    description="Generate a custom meme with top and bottom text"
)
@app_commands.describe(
    top_text="Text for top of meme",
    bottom_text="Text for bottom of meme", 
    template="Optional: Specific meme template name",
    custom_url="Optional: Custom image URL to create meme from",
    search="Optional: Search for a meme template using keywords"
)
async def memegen_command(
    interaction: discord.Interaction,
    top_text: str,
    bottom_text: str,
    template: Optional[str] = None,
    custom_url: Optional[str] = None,
    search: Optional[str] = None
):
    await interaction.response.defer()

    try:
        # Handle meme search and generation
        if search:
            try:
                from engine.commands.utility import search_ddg
                search_query = f"{search} meme template"
                results = await search_ddg(search_query, num_results=5, search_type='image')
                
                if not results:
                    await interaction.followup.send("❌ No meme templates found.")
                    return

                # Try each image URL until one works
                success = False
                for _, _, _, img_url in results:
                    try:
                        # Download and process image
                        image = await download_image(img_url)
                        if not image:
                            continue
                            
                        image = add_text_to_image(image, top_text, bottom_text)
                        
                        # Convert to bytes for Discord upload
                        with io.BytesIO() as image_binary:
                            image.save(image_binary, 'PNG')
                            image_binary.seek(0)
                            
                            # Send as Discord attachment
                            file = discord.File(fp=image_binary, filename='meme.png')
                            embed = discord.Embed(
                                title="Generated Meme",
                                description=f"Search query: {search}",
                                color=discord.Color.blue()
                            )
                            embed.set_image(url="attachment://meme.png")
                            await interaction.followup.send(embed=embed, file=file)
                            success = True
                            break
                            
                    except Exception as e:
                        print(f"Failed with image {img_url}: {e}")
                        continue
                        
                if not success:
                    await interaction.followup.send("❌ Failed to generate meme with any of the found templates.")
                return

            except Exception as e:
                print(f"Meme search error: {e}")
                await interaction.followup.send("❌ Failed to search for meme templates.")
                return
            
        if custom_url:
            try:
                # Download and process image
                image = await download_image(custom_url)
                image = add_text_to_image(image, top_text, bottom_text)
                
                # Convert to bytes for Discord upload
                with io.BytesIO() as image_binary:
                    image.save(image_binary, 'PNG')
                    image_binary.seek(0)
                    
                    # Send as Discord attachment
                    file = discord.File(fp=image_binary, filename='meme.png')
                    embed = discord.Embed(title="Generated Meme", color=discord.Color.blue())
                    embed.set_image(url="attachment://meme.png")
                    await interaction.followup.send(embed=embed, file=file)
                    
            except Exception as e:
                print(f"Error generating custom meme: {str(e)}")
                await interaction.followup.send(
                    "❌ Failed to generate meme. Make sure the image URL is valid.",
                    ephemeral=True
                )
            return
        
        # Template-based meme generation
        if template:
            # Try finding template on Imgflip first
            async with aiohttp.ClientSession() as session:
                imgflip_template = await find_imgflip_template(session, template)
                if imgflip_template:
                    # Generate meme using Imgflip template
                    params = {
                        'template_id': imgflip_template['id'],
                        'username': IMGFLIP_USERNAME,
                        'password': IMGFLIP_PASSWORD,
                        'text0': top_text,
                        'text1': bottom_text
                    }
                    
                    async with session.post('https://api.imgflip.com/caption_image', data=params) as resp:
                        data = await resp.json()
                        if not data['success']:
                            await interaction.followup.send("Failed to generate meme.", ephemeral=True)
                            return
                            
                        embed = discord.Embed(
                            title="Generated Meme",
                            description=f"Template: {imgflip_template['name']}",
                            color=discord.Color.blue()
                        )
                        embed.set_image(url=data['data']['url'])
                        await interaction.followup.send(embed=embed)
                        return
                # If not found on Imgflip, try local templates
                meme_template = find_template(template, MEME_TEMPLATES)
                if not meme_template:
                    await interaction.followup.send(f"❌ Template not found: {template}")
                    return
        else:
            # Use Imgflip API to generate a meme with a random template
            try:
                async with aiohttp.ClientSession() as session:
                    # Fetch list of memes from Imgflip
                    async with session.get('https://api.imgflip.com/get_memes') as resp:
                        data = await resp.json()
                        if not data['success']:
                            await interaction.followup.send("Failed to fetch memes from Imgflip.", ephemeral=True)
                            return
                        memes = data['data']['memes']
                        # Select a random meme template
                        meme_template = random.choice(memes)
                        template_id = meme_template['id']
                        template_name = meme_template['name']

                    # Generate meme using the selected template
                    params = {
                        'template_id': template_id,
                        'username': IMGFLIP_USERNAME,
                        'password': IMGFLIP_PASSWORD,
                        'text0': top_text,
                        'text1': bottom_text
                    }
                    async with session.post('https://api.imgflip.com/caption_image', data=params) as resp:
                        data = await resp.json()
                        if not data['success']:
                            await interaction.followup.send("Failed to generate meme with Imgflip.", ephemeral=True)
                            return
                        meme_url = data['data']['url']

                    embed = discord.Embed(
                        title="Generated Meme",
                        description=f"Template: {template_name}",
                        color=discord.Color.blue()
                    )
                    embed.set_image(url=meme_url)
                    await interaction.followup.send(embed=embed)

            except Exception as e:
                print(f"Error generating meme: {str(e)}")
                await interaction.followup.send(
                    "❌ Failed to generate meme. Please try again later.",
                    ephemeral=True
                )
            return
        
        # Convert template name to URL format and encode text
        meme_template = clean_template_name(meme_template)
        encoded_top = urllib.parse.quote(top_text)
        encoded_bottom = urllib.parse.quote(bottom_text)
        
        url = f"http://apimeme.com/meme?meme={meme_template}&top={encoded_top}&bottom={encoded_bottom}"

        embed = discord.Embed(
            title="Generated Meme",
            description=f"Template: {template or 'Random'}",
            color=discord.Color.blue()
        )
        embed.set_image(url=url)
        embed.set_footer(
            text=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error generating meme: {str(e)}")
        await interaction.followup.send(
            "❌ Failed to generate meme. Please try again later.",
            ephemeral=True
        )

async def search_sound_effects(query: str) -> list:
    """Search MyInstants for sound effects"""
    search_url = f'http://www.myinstants.com/search/?name={quote(query)}'
    
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as response:
            if response.status != 200:
                return []
                
            soup = BeautifulSoup(await response.text(), 'html.parser')
            results = []
            
            for instant in soup.find_all("div", class_="instant"):
                button_name = instant.find("a", class_="instant-link")
                button_name = button_name.text.strip() if button_name else "Unknown"
                
                small_button = instant.find("button", class_="small-button")
                if small_button and 'onclick' in small_button.attrs:
                    onclick = small_button['onclick']
                    # Fix URL extraction
                    button_url = onclick.split("'")[1]  # Get first quoted string
                    if button_url.endswith('.mp3'):
                        results.append({
                            "name": button_name,
                            "url": f"https://www.myinstants.com{button_url}"
                        })
            
            return results[:10]  # Limit to first 10 results

async def download_sound(url: str, session: aiohttp.ClientSession) -> bytes:
    """Download sound with proper headers"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'audio/mpeg, audio/*, */*',
        'Accept-Encoding': 'gzip, deflate',  # Changed from identity
        'Connection': 'keep-alive',
        'Referer': 'https://www.myinstants.com/'
        # Removed Range header to get full content
    }
    
    async with session.get(url, headers=headers) as response:
        if response.status not in (200, 206):  # Accept both 200 and 206
            raise Exception(f"Failed to download sound: {response.status}")
        return await response.read()
    
NUMBER_EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

class SoundboardView(discord.ui.View):
    def __init__(self, results: list, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.results = results
        self.original_interaction = interaction
        
        # Add button for each result
        for i, result in enumerate(results):
            button = discord.ui.Button(
                label=result['name'],
                emoji=NUMBER_EMOJIS[i] if i < len(NUMBER_EMOJIS) else None,
                style=discord.ButtonStyle.primary,
                custom_id=f"sound_{i}"
            )
            button.callback = self.create_callback(i)
            self.add_item(button)
    
    def create_callback(self, index):
        async def button_callback(interaction: discord.Interaction):
            if not interaction.user.voice:
                try:
                    await interaction.response.send_message(
                        "❌ You need to be in a voice channel!", 
                        ephemeral=True
                    )
                except discord.errors.InteractionResponded:
                    await interaction.followup.send(
                        "❌ You need to be in a voice channel!",
                        ephemeral=True
                    )
                return

            sound_url = self.results[index]['url']
            temp_path = None
            
            try:
                # Connect to voice if not already connected
                if not interaction.guild.voice_client:
                    voice_channel = interaction.user.voice.channel
                    await voice_channel.connect()
                
                # Acknowledge the interaction first
                try:
                    await interaction.response.defer(ephemeral=True)
                except discord.errors.InteractionResponded:
                    pass

                # Create temp file
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    temp_path = tmp.name
                    
                    # Download sound
                    async with aiohttp.ClientSession() as session:
                        async with session.get(sound_url, headers={
                            'User-Agent': 'Mozilla/5.0',
                            'Accept': '*/*'
                        }) as response:
                            if response.status != 200:
                                raise Exception(f"Failed to download sound: {response.status}")
                            
                            # Write to temp file
                            async with aiofiles.open(temp_path, 'wb') as f:
                                await f.write(await response.read())
                
                # Create audio source
                source = await discord.FFmpegOpusAudio.from_probe(
                    temp_path,
                    options='-filter:a volume=2.0'
                )
                
                # Play audio
                if interaction.guild.voice_client.is_playing():
                    interaction.guild.voice_client.stop()
                
                def after_playing(error):
                    if error:
                        logging.error(f"Playback error: {error}")
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                    except Exception as e:
                        logging.error(f"Cleanup error: {e}")
                
                interaction.guild.voice_client.play(source, after=after_playing)
                await interaction.followup.send(
                    f"▶️ Now playing: {self.results[index]['name']}",
                    ephemeral=True
                )
                
            except Exception as e:
                logging.error(f"Sound playback error: {e}")
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                try:
                    await interaction.followup.send(
                        f"❌ Error: {str(e)}",
                        ephemeral=True
                    )
                except Exception:
                    pass
                    
        return button_callback

@app_commands.command(
    name="soundboard",
    description="Search and play sound effects from MyInstants"
)
@app_commands.describe(
    query="Sound effect to search for",
    play="Immediately play the first result"
)
async def soundboard_command(interaction: discord.Interaction, query: str, play: Optional[bool] = False):
    await interaction.response.defer()
    
    try:
        results = await search_sound_effects(query)
        
        if not results:
            await interaction.followup.send("❌ No sound effects found.")
            return

        embed = discord.Embed(
            title="🔊 Sound Effects",
            description=f"Search results for '{query}'",
            color=discord.Color.blue()
        )
        
        for i, result in enumerate(results, 1):
            embed.add_field(
            name=f"{i}. {result['name']}",
            value=f"[Click here to download]({result['url']})",
            inline=False
            )
        
        view = SoundboardView(results, interaction)
        await interaction.followup.send(embed=embed, view=view)
        
        # Handle play=True option
        if play and results:
            await view.create_callback(0)(interaction)
            
    except Exception as e:
        logging.error(f"Soundboard error: {e}")
        await interaction.followup.send(
            f"❌ Error: {str(e)}",
            ephemeral=True
        )