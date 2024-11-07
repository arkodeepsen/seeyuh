import discord, random, httpx, aiohttp, asyncio
from discord import app_commands
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
    await interaction.response.send_message(f"\n{question} \n🎱 {response}")
    
@app_commands.command(name="choose", description="Let the bot choose between multiple options!")
async def choose_command(interaction: discord.Interaction, options: str):
    # Split the options by commas
    option_list = [option.strip() for option in options.split(",")]

    # Choose a random option
    response = random.choice(option_list)

    # Send the chosen option as a reply
    await interaction.response.send_message(f"I choose: {response}")
    
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
    correct_answer = trivia[question]
    
    # Send the trivia question as a reply
    await interaction.response.send_message(f"**Trivia Question:** {question}")

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        # Wait for the user's response
        user_response = await interaction.client.wait_for('message', check=check, timeout=30.0)
        
        # Check if the answer is correct
        if correct_answer.lower() in user_response.content.strip().lower():
            await interaction.followup.send(f"Correct! 🎉 The answer is indeed {correct_answer}.")
        else:
            await interaction.followup.send(f"Sorry, that's incorrect. The correct answer is {correct_answer}.")
    except asyncio.TimeoutError:
        await interaction.followup.send(f"You took too long to respond! The correct answer was {correct_answer}.")

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
