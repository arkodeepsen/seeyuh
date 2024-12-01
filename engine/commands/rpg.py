"""
import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
from supabase import create_client, Client

# Supabase client setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Character creation
@app_commands.command(name="create_character", description="Create your RPG character.")
async def create_character(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    # Check if user already exists in Supabase
    response = supabase.table('users').select('user_id').eq('user_id', user_id).execute()
    if response.data:
        await interaction.response.send_message("You already have a character!", ephemeral=True)
        return
    
    # Insert new user into Supabase
    user_data = {
        "user_id": user_id,
        "name": interaction.user.name,
        "level": 1,
        "experience": 0,
        "health": 100,
        "attack": 10,
        "defense": 5,
        "money": 1000
    }
    supabase.table('users').insert(user_data).execute()
    
    await interaction.response.send_message("Character created successfully!", ephemeral=True)

@app_commands.command(name="profile", description="View your profile and inventory.")
async def profile(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    # Fetch user data
    response = supabase.table('users').select('*').eq('user_id', user_id).execute()
    if not response.data:
        await interaction.response.send_message("You don't have a character yet. Use `/create_character` to create one.", ephemeral=True)
        return
    user_data = response.data[0]
    
    # Fetch user inventory
    inventory_response = supabase.table('user_items').select('item_id', 'quantity') \
        .eq('user_id', user_id).execute()
    inventory_items = inventory_response.data if inventory_response.data else []
    
    # Build inventory string
    inventory_str = "\n".join([f"{item['item_id']}: {item['quantity']}" for item in inventory_items]) or "No items"
    
    # Create embed
    embed = discord.Embed(title=f"{user_data['name']}'s Profile", color=discord.Color.blue())
    embed.add_field(name="Level", value=user_data['level'])
    embed.add_field(name="Experience", value=user_data['experience'])
    embed.add_field(name="Health", value=user_data['health'])
    embed.add_field(name="Attack", value=user_data['attack'])
    embed.add_field(name="Defense", value=user_data['defense'])
    embed.add_field(name="Money", value=user_data['money'])
    embed.add_field(name="Inventory", value=inventory_str, inline=False)
    
    await interaction.response.send_message(embed=embed)
    
# View character stats
@app_commands.command(name="stats", description="View your character's stats.")
async def stats(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    
    if user_id not in data:
        await interaction.response.send_message("You don't have a character yet. Use /create_character to create one.", ephemeral=True)
        return
    
    character = data[user_id]
    embed = discord.Embed(title=f"{character['name']}'s Stats", color=discord.Color.blue())
    embed.add_field(name="Level", value=character["level"])
    embed.add_field(name="Experience", value=character["experience"])
    embed.add_field(name="Health", value=character["health"])
    embed.add_field(name="Attack", value=character["attack"])
    embed.add_field(name="Defense", value=character["defense"])
    embed.add_field(name="Money", value=character["money"])
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Earn money
@app_commands.command(name="work", description="Work to earn money.")
async def work(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    # Fetch user data
    response = supabase.table('users').select('money').eq('user_id', user_id).execute()
    if not response.data:
        await interaction.response.send_message("You don't have a character yet. Use `/create_character` to create one.", ephemeral=True)
        return
    
    earnings = random.randint(100, 500)
    new_balance = response.data[0]['money'] + earnings
    
    # Update user's money
    supabase.table('users').update({'money': new_balance}).eq('user_id', user_id).execute()
    
    await interaction.response.send_message(f"You worked hard and earned {earnings} coins!", ephemeral=True)

@app_commands.command(name="acquire", description="Acquire an item.")
@app_commands.describe(item_id="ID of the item to acquire.", quantity="Quantity of the item.")
async def acquire(interaction: discord.Interaction, item_id: str, quantity: int):
    user_id = str(interaction.user.id)
    
    # Check if item exists
    item_response = supabase.table('items').select('*').eq('item_id', item_id).execute()
    if not item_response.data:
        await interaction.response.send_message("Item does not exist.", ephemeral=True)
        return
    
    # Insert or update item in user inventory
    user_item_response = supabase.table('user_items').select('quantity') \
        .eq('user_id', user_id).eq('item_id', item_id).execute()
    
    if user_item_response.data:
        # Update quantity
        new_quantity = user_item_response.data[0]['quantity'] + quantity
        supabase.table('user_items').update({'quantity': new_quantity}) \
            .eq('user_id', user_id).eq('item_id', item_id).execute()
    else:
        # Insert new item
        supabase.table('user_items').insert({
            'user_id': user_id,
            'item_id': item_id,
            'quantity': quantity
        }).execute()
    
    await interaction.response.send_message(f"You have acquired {quantity} x {item_id}.", ephemeral=True)
    
@app_commands.command(name="inventory", description="View your inventory.")
async def inventory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    # Fetch user inventory
    inventory_response = supabase.table('user_items').select('item_id', 'quantity') \
        .eq('user_id', user_id).execute()
    inventory_items = inventory_response.data if inventory_response.data else []
    
    if not inventory_items:
        await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
        return
    
    inventory_str = "\n".join([f"{item['item_id']}: {item['quantity']}" for item in inventory_items])
    embed = discord.Embed(title=f"{interaction.user.name}'s Inventory", description=inventory_str, color=discord.Color.purple())
    await interaction.response.send_message(embed=embed)
    
@app_commands.command(name="buy_stock", description="Buy stocks from the market.")
@app_commands.describe(stock_symbol="Symbol of the stock to buy.", quantity="Number of shares to buy.")
async def buy_stock(interaction: discord.Interaction, stock_symbol: str, quantity: int):
    user_id = str(interaction.user.id)
    
    # Fetch stock data
    stock_response = supabase.table('stocks').select('*').eq('symbol', stock_symbol).execute()
    if not stock_response.data:
        await interaction.response.send_message("Stock not found.", ephemeral=True)
        return
    stock = stock_response.data[0]
    total_price = stock['price'] * quantity
    
    # Fetch user data
    user_response = supabase.table('users').select('money').eq('user_id', user_id).execute()
    user_money = user_response.data[0]['money']
    
    if user_money < total_price:
        await interaction.response.send_message("You don't have enough money to buy these stocks.", ephemeral=True)
        return
    
    # Update user's money
    supabase.table('users').update({'money': user_money - total_price}).eq('user_id', user_id).execute()
    
    # Insert or update user's stock holdings
    holding_response = supabase.table('user_stocks').select('quantity') \
        .eq('user_id', user_id).eq('stock_symbol', stock_symbol).execute()
    if holding_response.data:
        new_quantity = holding_response.data[0]['quantity'] + quantity
        supabase.table('user_stocks').update({'quantity': new_quantity}) \
            .eq('user_id', user_id).eq('stock_symbol', stock_symbol).execute()
    else:
        supabase.table('user_stocks').insert({
            'user_id': user_id,
            'stock_symbol': stock_symbol,
            'quantity': quantity
        }).execute()
    
    await interaction.response.send_message(f"You bought {quantity} shares of {stock_symbol}.", ephemeral=True)
    
@app_commands.command(name="stocks", description="View available stocks and their prices.")
async def stocks(interaction: discord.Interaction):
    stocks_response = supabase.table('stocks').select('*').execute()
    stocks = stocks_response.data if stocks_response.data else []
    
    if not stocks:
        await interaction.response.send_message("No stocks are currently available.", ephemeral=True)
        return
    
    stocks_str = "\n".join([f"{stock['symbol']}: ${stock['price']}" for stock in stocks])
    embed = discord.Embed(title="Stock Market", description=stocks_str, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)
    
# Battle system
@app_commands.command(name="battle", description="Battle another player.")
@app_commands.describe(opponent="The player you want to battle.")
async def battle(interaction: discord.Interaction, opponent: discord.Member):
    data = load_data()
    user_id = str(interaction.user.id)
    opponent_id = str(opponent.id)
    
    if user_id not in data or opponent_id not in data:
        await interaction.response.send_message("Both players need to have a character to battle.", ephemeral=True)
        return
    
    player = data[user_id]
    enemy = data[opponent_id]
    
    player_health = player["health"]
    enemy_health = enemy["health"]
    
    while player_health > 0 and enemy_health > 0:
        enemy_health -= max(0, player["attack"] - enemy["defense"])
        if enemy_health <= 0:
            break
        player_health -= max(0, enemy["attack"] - player["defense"])
    
    if player_health > 0:
        winner = interaction.user.name
        loser = opponent.name
    else:
        winner = opponent.name
        loser = interaction.user.name
    
    await interaction.response.send_message(f"{winner} won the battle against {loser}!", ephemeral=True)

# Social interaction: Gift money
@app_commands.command(name="gift", description="Gift money to another player.")
@app_commands.describe(amount="Amount of money to gift.", recipient="The player to gift money to.")
async def gift(interaction: discord.Interaction, amount: int, recipient: discord.Member):
    data = load_data()
    user_id = str(interaction.user.id)
    recipient_id = str(recipient.id)
    
    if user_id not in data or recipient_id not in data:
        await interaction.response.send_message("Both players need to have a character to gift money.", ephemeral=True)
        return
    
    if data[user_id]["money"] < amount:
        await interaction.response.send_message("You don't have enough money to gift.", ephemeral=True)
        return
    
    data[user_id]["money"] -= amount
    data[recipient_id]["money"] += amount
    save_data(data)
    
    await interaction.response.send_message(f"You gifted {amount} coins to {recipient.name}!", ephemeral=True)
"""