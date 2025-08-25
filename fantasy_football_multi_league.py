#!/usr/bin/env python3
"""
Fantasy Football MCP Server - Multi-League Support
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

import aiohttp
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

# Reddit sentiment analysis imports
try:
    import praw
    from textblob import TextBlob
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False

# Import rate limiting and caching utilities
from src.yahoo_api_utils import rate_limiter, response_cache

# Draft functionality is built-in (no complex imports needed)
DRAFT_AVAILABLE = True

# Load environment
load_dotenv()

# Configuration
YAHOO_ACCESS_TOKEN = os.getenv("YAHOO_ACCESS_TOKEN")
YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"

# Reddit configuration
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")

# Create server instance
server = Server("fantasy-football")

# Cache for leagues
LEAGUES_CACHE = {}


async def yahoo_api_call(endpoint: str, retry_on_auth_fail: bool = True, use_cache: bool = True) -> dict:
    """Make Yahoo API request with rate limiting, caching, and automatic token refresh."""
    global YAHOO_ACCESS_TOKEN
    
    # Check cache first (if enabled)
    if use_cache:
        cached_response = await response_cache.get(endpoint)
        if cached_response is not None:
            return cached_response
    
    # Apply rate limiting
    await rate_limiter.acquire()
    
    url = f"{YAHOO_API_BASE}/{endpoint}?format=json"
    headers = {
        "Authorization": f"Bearer {YAHOO_ACCESS_TOKEN}",
        "Accept": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                # Cache successful response
                if use_cache:
                    await response_cache.set(endpoint, data)
                return data
            elif response.status == 401 and retry_on_auth_fail:
                # Token expired, try to refresh
                refresh_result = await refresh_yahoo_token()
                if refresh_result.get("status") == "success":
                    # Token refreshed, retry the API call with new token
                    return await yahoo_api_call(endpoint, retry_on_auth_fail=False, use_cache=use_cache)
                else:
                    # Refresh failed, raise the original error
                    text = await response.text()
                    raise Exception(f"Yahoo API auth failed and token refresh failed: {text[:200]}")
            else:
                text = await response.text()
                raise Exception(f"Yahoo API error {response.status}: {text[:200]}")


async def refresh_yahoo_token() -> dict:
    """Refresh the Yahoo access token using the refresh token."""
    global YAHOO_ACCESS_TOKEN
    
    client_id = os.getenv("YAHOO_CONSUMER_KEY")
    client_secret = os.getenv("YAHOO_CONSUMER_SECRET")
    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        return {
            "status": "error",
            "message": "Missing credentials in environment"
        }
    
    token_url = "https://api.login.yahoo.com/oauth2/get_token"
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    new_access_token = token_data.get("access_token")
                    new_refresh_token = token_data.get("refresh_token", refresh_token)
                    expires_in = token_data.get("expires_in", 3600)
                    
                    # Update global token
                    YAHOO_ACCESS_TOKEN = new_access_token
                    
                    # Update environment
                    os.environ["YAHOO_ACCESS_TOKEN"] = new_access_token
                    if new_refresh_token != refresh_token:
                        os.environ["YAHOO_REFRESH_TOKEN"] = new_refresh_token
                    
                    return {
                        "status": "success",
                        "message": "Token refreshed successfully",
                        "expires_in": expires_in,
                        "expires_in_hours": round(expires_in / 3600, 1)
                    }
                else:
                    error_text = await response.text()
                    return {
                        "status": "error",
                        "message": f"Failed to refresh token: {response.status}",
                        "details": error_text[:200]
                    }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error refreshing token: {str(e)}"
        }


async def discover_leagues() -> Dict[str, Dict[str, Any]]:
    """Discover all active NFL leagues for the authenticated user."""
    global LEAGUES_CACHE
    
    if LEAGUES_CACHE:
        return LEAGUES_CACHE
    
    # Get current NFL leagues (game key 461 for 2025)
    data = await yahoo_api_call("users;use_login=1/games;game_keys=nfl/leagues")
    
    leagues = {}
    try:
        users = data.get("fantasy_content", {}).get("users", {})
        
        if "0" in users:
            user = users["0"]["user"]
            
            if isinstance(user, list):
                for item in user:
                    if isinstance(item, dict) and "games" in item:
                        games = item["games"]
                        
                        if "0" in games:  # First game (NFL)
                            game = games["0"]["game"]
                            if isinstance(game, list):
                                for g in game:
                                    if isinstance(g, dict) and "leagues" in g:
                                        league_data = g["leagues"]
                                        
                                        for key in league_data:
                                            if key != "count" and isinstance(league_data[key], dict):
                                                if "league" in league_data[key]:
                                                    league_info = league_data[key]["league"]
                                                    if isinstance(league_info, list) and len(league_info) > 0:
                                                        league_dict = league_info[0]
                                                        
                                                        league_key = league_dict.get("league_key", "")
                                                        leagues[league_key] = {
                                                            "key": league_key,
                                                            "id": league_dict.get("league_id", ""),
                                                            "name": league_dict.get("name", "Unknown"),
                                                            "season": league_dict.get("season", 2025),
                                                            "num_teams": league_dict.get("num_teams", 0),
                                                            "scoring_type": league_dict.get("scoring_type", "head"),
                                                            "current_week": league_dict.get("current_week", 1),
                                                            "is_finished": league_dict.get("is_finished", 0)
                                                        }
    except Exception as e:
        pass  # Silently handle error to not interfere with MCP protocol
    
    LEAGUES_CACHE = leagues
    return leagues


async def get_user_team_info(league_key: str) -> Optional[dict]:
    """Get the user's team key and name in a specific league."""
    try:
        data = await yahoo_api_call(f"league/{league_key}/teams")
        
        # Get user's GUID from environment
        user_guid = os.getenv("YAHOO_GUID", "QQQ5VN577FJJ4GT2NLMJMIYEBU")
        
        # Parse to find user's team
        league = data.get("fantasy_content", {}).get("league", [])
        
        if len(league) > 1 and isinstance(league[1], dict) and "teams" in league[1]:
            teams = league[1]["teams"]
            
            for key in teams:
                if key != "count" and isinstance(teams[key], dict):
                    if "team" in teams[key]:
                        team_array = teams[key]["team"]
                        
                        if isinstance(team_array, list) and len(team_array) > 0:
                            # The team data is in the first element
                            team_data = team_array[0]
                            
                            if isinstance(team_data, list):
                                team_key = None
                                team_name = None
                                is_users_team = False
                                draft_grade = None
                                draft_position = None
                                
                                # Parse each element in the team data
                                for element in team_data:
                                    if isinstance(element, dict):
                                        # Check for team key
                                        if "team_key" in element:
                                            team_key = element["team_key"]
                                        
                                        # Get team name
                                        if "name" in element:
                                            team_name = element["name"]
                                        
                                        # Get draft grade
                                        if "draft_grade" in element:
                                            draft_grade = element["draft_grade"]
                                        
                                        # Get draft position
                                        if "draft_position" in element:
                                            draft_position = element["draft_position"]
                                        
                                        # Check if owned by current login
                                        if "is_owned_by_current_login" in element and element["is_owned_by_current_login"] == 1:
                                            is_users_team = True
                                        
                                        # Also check by GUID
                                        if "managers" in element:
                                            managers = element["managers"]
                                            if managers and len(managers) > 0:
                                                mgr = managers[0].get("manager", {})
                                                if mgr.get("guid") == user_guid:
                                                    is_users_team = True
                                
                                if is_users_team and team_key:
                                    return {
                                        "team_key": team_key,
                                        "team_name": team_name,
                                        "draft_grade": draft_grade,
                                        "draft_position": draft_position
                                    }
        
        return None
    except Exception as e:
        # Silently handle error to not interfere with MCP protocol
        return None


async def get_user_team_key(league_key: str) -> Optional[str]:
    """Get the user's team key in a specific league (legacy function for compatibility)."""
    team_info = await get_user_team_info(league_key)
    return team_info.get("team_key") if team_info else None


async def get_waiver_wire_players(league_key: str, position: str = "all", sort: str = "rank", count: int = 20) -> List[dict]:
    """Get available waiver wire players with detailed stats."""
    try:
        # Build the API call with filters
        pos_filter = f";position={position}" if position != "all" else ""
        sort_type = {
            "rank": "OR",  # Overall rank
            "points": "PTS",  # Points
            "owned": "O",  # Ownership %
            "trending": "A"  # Added %
        }.get(sort, "OR")
        
        endpoint = f"league/{league_key}/players;status=A{pos_filter};sort={sort_type};count={count}"
        data = await yahoo_api_call(endpoint)
        
        players = []
        league = data.get("fantasy_content", {}).get("league", [])
        
        # Players are in the second element of the league array
        if len(league) > 1 and isinstance(league[1], dict) and "players" in league[1]:
            players_data = league[1]["players"]
            
            for key in players_data:
                if key != "count" and isinstance(players_data[key], dict):
                    if "player" in players_data[key]:
                        player_array = players_data[key]["player"]
                        
                        # Player data is in nested array structure
                        if isinstance(player_array, list) and len(player_array) > 0:
                            player_data = player_array[0]
                            
                            if isinstance(player_data, list):
                                player_info = {}
                                
                                for element in player_data:
                                    if isinstance(element, dict):
                                        # Basic info
                                        if "name" in element:
                                            player_info["name"] = element["name"]["full"]
                                        if "player_key" in element:
                                            player_info["player_key"] = element["player_key"]
                                        if "editorial_team_abbr" in element:
                                            player_info["team"] = element["editorial_team_abbr"]
                                        if "display_position" in element:
                                            player_info["position"] = element["display_position"]
                                        if "bye_weeks" in element:
                                            player_info["bye"] = element["bye_weeks"].get("week", "N/A")
                                        
                                        # Ownership data
                                        if "ownership" in element:
                                            ownership = element["ownership"]
                                            player_info["owned_pct"] = ownership.get("ownership_percentage", 0)
                                            player_info["weekly_change"] = ownership.get("weekly_change", 0)
                                        
                                        # Injury status
                                        if "status" in element:
                                            player_info["injury_status"] = element["status"]
                                        if "status_full" in element:
                                            player_info["injury_detail"] = element["status_full"]
                                
                                if player_info.get("name"):
                                    players.append(player_info)
        
        return players
    except Exception as e:
        return []


async def get_draft_rankings(league_key: str = None, position: str = "all", count: int = 50) -> List[dict]:
    """Get pre-draft rankings with ADP data."""
    try:
        # If no league key provided, get the first available league
        if not league_key:
            leagues = await discover_leagues()
            if leagues:
                league_key = list(leagues.keys())[0]
            else:
                return []  # No leagues available
        
        pos_filter = f";position={position}" if position != "all" else ""
        
        # Get all players sorted by rank for the specified league
        endpoint = f"league/{league_key}/players{pos_filter};sort=OR;count={count}"
        data = await yahoo_api_call(endpoint)
        
        players = []
        league = data.get("fantasy_content", {}).get("league", [])
        
        # Players are in the second element of the league array
        if len(league) > 1 and isinstance(league[1], dict) and "players" in league[1]:
            players_data = league[1]["players"]
            
            for key in players_data:
                if key != "count" and isinstance(players_data[key], dict):
                    if "player" in players_data[key]:
                        player_array = players_data[key]["player"]
                        
                        # Player data is in nested array structure
                        if isinstance(player_array, list) and len(player_array) > 0:
                            player_data = player_array[0]
                            
                            if isinstance(player_data, list):
                                player_info = {}
                                rank = int(key) + 1  # Use the key as rank
                                
                                for element in player_data:
                                    if isinstance(element, dict):
                                        if "name" in element:
                                            player_info["name"] = element["name"]["full"]
                                        if "editorial_team_abbr" in element:
                                            player_info["team"] = element["editorial_team_abbr"]
                                        if "display_position" in element:
                                            player_info["position"] = element["display_position"]
                                        if "bye_weeks" in element:
                                            player_info["bye"] = element["bye_weeks"].get("week", "N/A")
                                        
                                        # Draft data if available
                                        if "draft_analysis" in element:
                                            draft = element["draft_analysis"]
                                            player_info["average_draft_position"] = draft.get("average_pick", rank)
                                            player_info["average_round"] = draft.get("average_round", "N/A") 
                                            player_info["average_cost"] = draft.get("average_cost", "N/A")
                                            player_info["percent_drafted"] = draft.get("percent_drafted", 0)
                                        else:
                                            # Use rank as ADP if no draft data
                                            player_info["rank"] = rank
                                
                                if player_info.get("name"):
                                    players.append(player_info)
        
        # Sort by ADP if available
        players.sort(key=lambda x: float(x.get("average_draft_position", 999)) if x.get("average_draft_position") != "N/A" else 999)
        
        return players
    except Exception as e:
        return []


async def get_all_teams_info(league_key: str) -> List[dict]:
    """Get all teams information including draft data."""
    try:
        data = await yahoo_api_call(f"league/{league_key}/teams")
        
        teams_list = []
        league = data.get("fantasy_content", {}).get("league", [])
        
        if len(league) > 1 and isinstance(league[1], dict) and "teams" in league[1]:
            teams = league[1]["teams"]
            
            for key in teams:
                if key != "count" and isinstance(teams[key], dict):
                    if "team" in teams[key]:
                        team_array = teams[key]["team"]
                        
                        if isinstance(team_array, list) and len(team_array) > 0:
                            team_data = team_array[0]
                            
                            if isinstance(team_data, list):
                                team_info = {}
                                
                                for element in team_data:
                                    if isinstance(element, dict):
                                        if "team_key" in element:
                                            team_info["team_key"] = element["team_key"]
                                        if "team_id" in element:
                                            team_info["team_id"] = element["team_id"]
                                        if "name" in element:
                                            team_info["name"] = element["name"]
                                        if "draft_grade" in element:
                                            team_info["draft_grade"] = element["draft_grade"]
                                        if "draft_position" in element:
                                            team_info["draft_position"] = element["draft_position"]
                                        if "draft_recap_url" in element:
                                            team_info["draft_recap_url"] = element["draft_recap_url"]
                                        if "number_of_moves" in element:
                                            team_info["moves"] = element["number_of_moves"]
                                        if "number_of_trades" in element:
                                            team_info["trades"] = element["number_of_trades"]
                                        if "managers" in element:
                                            managers = element["managers"]
                                            if managers and len(managers) > 0:
                                                mgr = managers[0].get("manager", {})
                                                team_info["manager"] = mgr.get("nickname", "Unknown")
                                
                                if team_info.get("team_key"):
                                    teams_list.append(team_info)
        
        # Sort by draft position if available
        teams_list.sort(key=lambda x: x.get("draft_position", 999))
        return teams_list
        
    except Exception as e:
        return []


async def analyze_reddit_sentiment(players: List[str], time_window_hours: int = 48) -> Dict[str, Any]:
    """
    Analyze Reddit sentiment for fantasy football players.
    Used for Start/Sit decisions based on community consensus.
    """
    if not REDDIT_AVAILABLE:
        return {
            "error": "Reddit analysis not available. Install 'praw' and 'textblob' packages."
        }
    
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return {
            "error": "Reddit API credentials not configured"
        }
    
    try:
        # Initialize Reddit client
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=f'fantasy-football-mcp:v1.0 by /u/{REDDIT_USERNAME or "unknown"}'
        )
        
        results = {
            "players": players,
            "analysis_type": "comparison" if len(players) > 1 else "single",
            "time_window_hours": time_window_hours,
            "player_data": {}
        }
        
        subreddits = ["fantasyfootball", "DynastyFF", "Fantasy_Football", "nfl"]
        
        for player in players:
            player_sentiments = []
            total_posts = 0
            total_engagement = 0
            injury_mentions = 0
            relevant_comments = []
            
            # Search across subreddits
            for subreddit_name in subreddits:
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    posts = list(subreddit.search(player, time_filter='week', limit=5))
                    
                    for post in posts:
                        total_posts += 1
                        total_engagement += post.score + post.num_comments
                        
                        # Analyze sentiment
                        text = f"{post.title} {post.selftext[:500] if post.selftext else ''}"
                        blob = TextBlob(text)
                        sentiment = blob.sentiment.polarity
                        player_sentiments.append(sentiment)
                        
                        # Check for injuries
                        injury_keywords = ['injured', 'injury', 'out', 'doubtful', 'questionable', 'IR']
                        if any(keyword.lower() in text.lower() for keyword in injury_keywords):
                            injury_mentions += 1
                        
                        # Get top comments
                        if post.score > 10:
                            relevant_comments.append({
                                "text": post.title[:100],
                                "score": post.score,
                                "sentiment": sentiment
                            })
                except Exception:
                    continue
            
            # Calculate metrics
            avg_sentiment = sum(player_sentiments) / len(player_sentiments) if player_sentiments else 0
            
            # Determine consensus
            if avg_sentiment > 0.1:
                consensus = "START"
            elif avg_sentiment < -0.1:
                consensus = "SIT"
            else:
                consensus = "MIXED"
            
            # Calculate hype score (combination of sentiment and engagement)
            hype_score = ((avg_sentiment + 1) / 2) * min(total_engagement / 100, 1.0)
            
            results["player_data"][player] = {
                "sentiment_score": round(avg_sentiment, 3),
                "consensus": consensus,
                "posts_analyzed": total_posts,
                "total_engagement": total_engagement,
                "injury_mentions": injury_mentions,
                "hype_score": round(hype_score, 3),
                "top_comments": sorted(relevant_comments, key=lambda x: x["score"], reverse=True)[:3]
            }
        
        # Add comparison recommendation if multiple players
        if len(players) > 1:
            sorted_players = sorted(
                results["player_data"].items(),
                key=lambda x: x[1]["sentiment_score"] + x[1]["hype_score"],
                reverse=True
            )
            
            results["recommendation"] = {
                "start": sorted_players[0][0],
                "sit": [p[0] for p in sorted_players[1:]],
                "confidence": min(abs(sorted_players[0][1]["sentiment_score"] - 
                                     sorted_players[-1][1]["sentiment_score"]) * 100, 100)
            }
        
        return results
        
    except Exception as e:
        return {
            "error": f"Reddit analysis failed: {str(e)}"
        }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available fantasy football tools."""
    base_tools = [
        Tool(
            name="ff_get_leagues",
            description="Get all your fantasy football leagues",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="ff_get_league_info",
            description="Get detailed information about a specific league",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410'). Use ff_get_leagues to get available keys."
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_standings", 
            description="Get standings for a specific league",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_roster",
            description="Get your team roster in a specific league",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_matchup",
            description="Get matchup for a specific week in a league",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    },
                    "week": {
                        "type": "integer",
                        "description": "Week number (optional, defaults to current week)"
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_players",
            description="Get available free agent players in a league",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    },
                    "position": {
                        "type": "string",
                        "description": "Position filter (QB, RB, WR, TE, K, DEF)"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of players to return",
                        "default": 10
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_optimal_lineup",
            description="Get AI-optimized lineup recommendations for a league",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    },
                    "week": {
                        "type": "integer",
                        "description": "Week number (optional, defaults to current week)"
                    },
                    "strategy": {
                        "type": "string",
                        "description": "Strategy: 'conservative', 'aggressive', or 'balanced' (default: balanced)",
                        "enum": ["conservative", "aggressive", "balanced"]
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_refresh_token",
            description="Refresh the Yahoo API access token when it expires",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="ff_get_draft_results",
            description="Get draft results showing all teams with their draft positions and grades",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_waiver_wire",
            description="Get top available waiver wire players with detailed stats and projections",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    },
                    "position": {
                        "type": "string",
                        "description": "Position filter (QB, RB, WR, TE, K, DEF, or 'all')",
                        "enum": ["QB", "RB", "WR", "TE", "K", "DEF", "all"]
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort by: 'rank', 'points', 'owned', 'trending'",
                        "enum": ["rank", "points", "owned", "trending"],
                        "default": "rank"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of players to return (default: 20)",
                        "default": 20
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_api_status",
            description="Get Yahoo API rate limit status and cache statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="ff_clear_cache", 
            description="Clear the API response cache",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Optional pattern to match (e.g., 'standings', 'roster'). Clears all if not provided."
                    }
                }
            }
        ),
        Tool(
            name="ff_get_draft_rankings",
            description="Get pre-draft player rankings and ADP (Average Draft Position)",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (optional, uses first available league if not provided)"
                    },
                    "position": {
                        "type": "string",
                        "description": "Position filter (QB, RB, WR, TE, K, DEF, or 'all')",
                        "enum": ["QB", "RB", "WR", "TE", "K", "DEF", "all"],
                        "default": "all"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of players to return (default: 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="ff_get_opponent_roster_comparison",
            description="Get detailed comparison between your roster and opponent's roster for matchup analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    },
                    "week": {
                        "type": "integer",
                        "description": "Week number (optional, defaults to current week)"
                    }
                },
                "required": ["league_key"]
            }
        ),
        Tool(
            name="ff_get_all_teams",
            description="Get all teams in the league with their rosters for comparison",
            inputSchema={
                "type": "object",
                "properties": {
                    "league_key": {
                        "type": "string",
                        "description": "League key (e.g., '461.l.61410')"
                    }
                },
                "required": ["league_key"]
            }
        )
    ]
    
    # Add draft tools if available
    if DRAFT_AVAILABLE:
        draft_tools = [
            Tool(
                name="ff_get_draft_recommendation",
                description="Get AI-powered draft recommendations for live fantasy football drafts",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "league_key": {
                            "type": "string",
                            "description": "League key (e.g., '461.l.61410')"
                        },
                        "strategy": {
                            "type": "string",
                            "description": "Draft strategy: 'conservative', 'aggressive', or 'balanced' (default: balanced)",
                            "enum": ["conservative", "aggressive", "balanced"],
                            "default": "balanced"
                        },
                        "num_recommendations": {
                            "type": "integer", 
                            "description": "Number of top recommendations to return (1-20, default: 10)",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 10
                        },
                        "current_pick": {
                            "type": "integer",
                            "description": "Current overall pick number (optional)"
                        }
                    },
                    "required": ["league_key"]
                }
            ),
            Tool(
                name="ff_analyze_draft_state",
                description="Analyze current draft state including roster needs and strategic insights",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "league_key": {
                            "type": "string",
                            "description": "League key (e.g., '461.l.61410')"
                        },
                        "strategy": {
                            "type": "string", 
                            "description": "Draft strategy for analysis: 'conservative', 'aggressive', or 'balanced' (default: balanced)",
                            "enum": ["conservative", "aggressive", "balanced"],
                            "default": "balanced"
                        }
                    },
                    "required": ["league_key"]
                }
            ),
            Tool(
                name="ff_analyze_reddit_sentiment",
                description="Analyze Reddit sentiment for fantasy football players to help with Start/Sit decisions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "players": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of player names to analyze (e.g., ['Josh Allen', 'Jared Goff'])"
                        },
                        "time_window_hours": {
                            "type": "integer",
                            "description": "How far back to look for Reddit posts (default: 48 hours)",
                            "default": 48
                        }
                    },
                    "required": ["players"]
                }
            ),
            Tool(
                name="ff_get_opponent_roster",
                description="Get opponent team roster for the current week's matchup",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "league_key": {
                            "type": "string",
                            "description": "League key (e.g., '461.l.61410')"
                        },
                        "week": {
                            "type": "integer",
                            "description": "Week number (optional, defaults to current week)"
                        }
                    },
                    "required": ["league_key"]
                }
            )
        ]
        return base_tools + draft_tools
    
    return base_tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a fantasy football tool."""
    try:
        if name == "ff_get_leagues":
            # Get all leagues
            leagues = await discover_leagues()
            
            if not leagues:
                result = {
                    "error": "No active NFL leagues found",
                    "suggestion": "Make sure your Yahoo token is valid and you have active leagues"
                }
            else:
                result = {
                    "total_leagues": len(leagues),
                    "leagues": [
                        {
                            "key": league["key"],
                            "name": league["name"],
                            "teams": league["num_teams"],
                            "current_week": league["current_week"],
                            "scoring": league["scoring_type"]
                        }
                        for league in leagues.values()
                    ]
                }
            
        elif name == "ff_get_league_info":
            # Get specific league info
            league_key = arguments.get("league_key")
            
            # First check cache
            leagues = await discover_leagues()
            if league_key in leagues:
                league = leagues[league_key]
                
                # Get user's team info
                team_info = await get_user_team_info(league_key)
                
                # Get additional details
                data = await yahoo_api_call(f"league/{league_key}")
                result = {
                    "league": league["name"],
                    "key": league_key,
                    "season": league["season"],
                    "teams": league["num_teams"],
                    "current_week": league["current_week"],
                    "scoring_type": league["scoring_type"],
                    "status": "active" if not league["is_finished"] else "finished",
                    "your_team": {
                        "name": team_info.get("team_name", "Unknown") if team_info else "Not found",
                        "key": team_info.get("team_key") if team_info else None,
                        "draft_position": team_info.get("draft_position") if team_info else None,
                        "draft_grade": team_info.get("draft_grade") if team_info else None
                    }
                }
            else:
                result = {
                    "error": f"League {league_key} not found",
                    "available_leagues": list(leagues.keys())
                }
            
        elif name == "ff_get_standings":
            # Get standings
            league_key = arguments.get("league_key")
            data = await yahoo_api_call(f"league/{league_key}/standings")
            
            standings = []
            league = data.get("fantasy_content", {}).get("league", [])
            
            # Debug: Check the actual structure
            print(f"DEBUG: League type: {type(league)}")
            if isinstance(league, list):
                print(f"DEBUG: League list length: {len(league)}")
                for i, item in enumerate(league):
                    print(f"DEBUG: League[{i}] type: {type(item)}, keys: {list(item.keys()) if isinstance(item, dict) else 'Not a dict'}")
            elif isinstance(league, dict):
                print(f"DEBUG: League dict keys: {list(league.keys())}")
            
            # Try to find standings data in various possible locations
            standings_container = None
            
            # Method 1: Check if league is a dict with standings
            if isinstance(league, dict) and "standings" in league:
                standings_container = league["standings"]
                print("DEBUG: Found standings in league dict")
            
            # Method 2: Check if league is a list and look for standings
            elif isinstance(league, list):
                for i, item in enumerate(league):
                    if isinstance(item, dict) and "standings" in item:
                        standings_container = item["standings"]
                        print(f"DEBUG: Found standings in league[{i}]")
                        break
            
            # Method 3: Check if league is a list and standings might be at index 1
            elif isinstance(league, list) and len(league) > 1:
                if isinstance(league[1], dict) and "standings" in league[1]:
                    standings_container = league[1]["standings"]
                    print("DEBUG: Found standings in league[1]")
            
            if standings_container:
                print(f"DEBUG: Standings container type: {type(standings_container)}")
                if isinstance(standings_container, dict):
                    print(f"DEBUG: Standings container keys: {list(standings_container.keys())}")
                
                # Look for teams data in standings_container
                teams_data = None
                
                # Try different possible structures
                if isinstance(standings_container, dict):
                    if "teams" in standings_container:
                        teams_data = standings_container["teams"]
                        print("DEBUG: Found teams in standings.teams")
                    elif "0" in standings_container and isinstance(standings_container["0"], dict):
                        if "teams" in standings_container["0"]:
                            teams_data = standings_container["0"]["teams"]
                            print("DEBUG: Found teams in standings.0.teams")
                
                if teams_data:
                    print(f"DEBUG: Teams data type: {type(teams_data)}")
                    if isinstance(teams_data, dict):
                        print(f"DEBUG: Teams data keys: {list(teams_data.keys())}")
                    
                    # Parse teams data
                    if isinstance(teams_data, dict):
                        for key, value in teams_data.items():
                            if key == "count":
                                continue
                            if isinstance(value, dict) and "team" in value:
                                team_array = value["team"]
                                if isinstance(team_array, list) and len(team_array) > 0:
                                    team_name = None
                                    team_standings = {}
                                    
                                    for element in team_array:
                                        if isinstance(element, dict):
                                            if "name" in element:
                                                name_value = element["name"]
                                                team_name = name_value.get("full") if isinstance(name_value, dict) else name_value
                                            if "team_standings" in element and isinstance(element["team_standings"], dict):
                                                team_standings = element["team_standings"]
                                    
                                    if team_name and team_standings:
                                        standings.append({
                                            "rank": team_standings.get("rank", 0),
                                            "team": team_name,
                                            "wins": team_standings.get("outcome_totals", {}).get("wins", 0),
                                            "losses": team_standings.get("outcome_totals", {}).get("losses", 0),
                                            "ties": team_standings.get("outcome_totals", {}).get("ties", 0),
                                            "points_for": team_standings.get("points_for", 0),
                                            "points_against": team_standings.get("points_against", 0)
                                        })
 
            # Deep fallback: traverse entire payload to find any team arrays with team_standings
            if not standings:
                def traverse_and_collect(obj):
                    if isinstance(obj, dict):
                        # Direct team block
                        if "team" in obj and isinstance(obj["team"], list):
                            team_array = obj["team"]
                            team_name = None
                            team_st = {}
                            for el in team_array:
                                if isinstance(el, dict):
                                    if "name" in el:
                                        nv = el["name"]
                                        team_name = nv.get("full") if isinstance(nv, dict) else nv
                                    if "team_standings" in el and isinstance(el["team_standings"], dict):
                                        team_st = el["team_standings"]
                            if team_name:
                                standings.append({
                                    "rank": team_st.get("rank", 0),
                                    "team": team_name,
                                    "wins": team_st.get("outcome_totals", {}).get("wins", 0),
                                    "losses": team_st.get("outcome_totals", {}).get("losses", 0),
                                    "ties": team_st.get("outcome_totals", {}).get("ties", 0),
                                    "points_for": team_st.get("points_for", 0),
                                    "points_against": team_st.get("points_against", 0)
                                })
                        for v in obj.values():
                            traverse_and_collect(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            traverse_and_collect(v)
                try:
                    traverse_and_collect(data.get("fantasy_content", {}))
                except Exception:
                    pass

            # Final fallback: Use get_all_teams_info to build placeholder standings
            if not standings:
                try:
                    teams = await get_all_teams_info(league_key)
                    if teams:
                        # Assign ranks based on draft_position if available, else alphabetical
                        if any(t.get("draft_position") for t in teams):
                            teams_sorted = sorted(teams, key=lambda t: t.get("draft_position", 9999))
                        else:
                            teams_sorted = sorted(teams, key=lambda t: str(t.get("name", "")))
                        standings = [
                            {
                                "rank": idx + 1,
                                "team": (t.get("name", "Unknown").get("full") if isinstance(t.get("name"), dict) else t.get("name", "Unknown")),
                                "wins": 0,
                                "losses": 0,
                                "ties": 0,
                                "points_for": 0,
                                "points_against": 0
                            }
                            for idx, t in enumerate(teams_sorted)
                        ]
                except Exception:
                    pass

            # Sort by rank
            standings.sort(key=lambda x: x["rank"])
            
            result = {
                "league_key": league_key,
                "standings": standings,
                "debug_info": {
                    "total_teams_found": len(standings),
                    "league_structure": "logged_to_console"
                }
            }
            
        elif name == "ff_get_roster":
            # Get user's roster
            league_key = arguments.get("league_key")
            
            # Get user's team info
            team_info = await get_user_team_info(league_key)
            
            if team_info:
                team_key = team_info["team_key"]
                data = await yahoo_api_call(f"team/{team_key}/roster")
                
                roster = []
                team = data.get("fantasy_content", {}).get("team", [])
                
                # Look for roster data in the team array
                for item in team:
                    if isinstance(item, dict) and "roster" in item:
                        roster_data = item["roster"]
                        # Roster data is typically in the "0" key
                        if "0" in roster_data and "players" in roster_data["0"]:
                            players = roster_data["0"]["players"]
                            
                            for key in players:
                                if key != "count" and isinstance(players[key], dict):
                                    if "player" in players[key]:
                                        player_array = players[key]["player"]
                                        if isinstance(player_array, list) and len(player_array) > 0:
                                            player_info = {}
                                            
                                            # Player data is in nested array structure (similar to available players)
                                            if isinstance(player_array[0], list):
                                                player_data = player_array[0]
                                                
                                                for element in player_data:
                                                    if isinstance(element, dict):
                                                        # Basic info
                                                        if "name" in element:
                                                            name_val = element["name"]
                                                            if isinstance(name_val, dict):
                                                                player_info["name"] = name_val.get("full") or name_val.get("first")
                                                            elif isinstance(name_val, str):
                                                                player_info["name"] = name_val
                                                        # Position - try multiple fields
                                                        if "selected_position" in element:
                                                            sel = element["selected_position"]
                                                            if isinstance(sel, list) and len(sel) > 0:
                                                                if isinstance(sel[0], dict):
                                                                    player_info["position"] = sel[0].get("position") or sel[0].get("position_type")
                                                                else:
                                                                    player_info["position"] = str(sel[0])
                                                            elif isinstance(sel, dict):
                                                                player_info["position"] = sel.get("position") or sel.get("position_type")
                                                        elif "display_position" in element:
                                                            player_info["position"] = element["display_position"]
                                                        elif "position" in element:
                                                            player_info["position"] = element["position"]
                                                        # Status
                                                        if "status" in element:
                                                            player_info["status"] = element.get("status", "OK")
                                                        elif "status_full" in element:
                                                            player_info["status"] = element.get("status_full", "OK")
                                            
                                            if player_info.get("name"):
                                                roster.append(player_info)
                
                result = {
                    "league_key": league_key,
                    "team_key": team_key,
                    "team_name": team_info.get("team_name", "Unknown"),
                    "draft_position": team_info.get("draft_position"),
                    "draft_grade": team_info.get("draft_grade"),
                    "roster": roster
                }
            else:
                result = {
                    "error": f"Could not find your team in league {league_key}"
                }
            
        elif name == "ff_get_matchup":
            # Get matchup
            league_key = arguments.get("league_key")
            week = arguments.get("week", None)
            
            # Get user's team key
            team_key = await get_user_team_key(league_key)
            
            if team_key:
                week_param = f";week={week}" if week else ""
                data = await yahoo_api_call(f"team/{team_key}/matchups{week_param}")
                
                # Return raw data for debugging
                result = {
                    "league_key": league_key,
                    "team_key": team_key,
                    "week": week or "current",
                    "message": "Matchup data retrieved",
                    "raw_data": data,
                    "data_structure": {
                        "keys": list(data.keys()) if data else [],
                        "fantasy_content_keys": list(data.get("fantasy_content", {}).keys()) if data else [],
                        "team_structure": type(data.get("fantasy_content", {}).get("team", None)).__name__ if data else "None"
                    }
                }
            else:
                result = {
                    "error": f"Could not find your team in league {league_key}"
                }
            
        elif name == "ff_get_players":
            # Get available players
            league_key = arguments.get("league_key")
            position = arguments.get("position", "")
            count = arguments.get("count", 10)
            
            pos_filter = f";position={position}" if position else ""
            # Include default sort parameter to match working waiver wire endpoint
            endpoint = f"league/{league_key}/players;status=A{pos_filter};sort=OR;count={count}"
            data = await yahoo_api_call(endpoint)
            
            players = []
            league = data.get("fantasy_content", {}).get("league", [])
            
            # Players are in the second element of the league array (index 1)
            if len(league) > 1 and isinstance(league[1], dict) and "players" in league[1]:
                players_data = league[1]["players"]
                
                for key in players_data:
                    if key != "count" and isinstance(players_data[key], dict):
                        if "player" in players_data[key]:
                            player_array = players_data[key]["player"]
                            
                            # Player data is in nested array structure
                            if isinstance(player_array, list) and len(player_array) > 0:
                                player_data = player_array[0]
                                
                                if isinstance(player_data, list):
                                    player_info = {}
                                    
                                    for element in player_data:
                                        if isinstance(element, dict):
                                            # Basic info
                                            if "name" in element:
                                                player_info["name"] = element["name"]["full"]
                                            if "player_key" in element:
                                                player_info["player_key"] = element["player_key"]
                                            if "editorial_team_abbr" in element:
                                                player_info["team"] = element["editorial_team_abbr"]
                                            if "display_position" in element:
                                                player_info["position"] = element["display_position"]
                                            if "bye_weeks" in element:
                                                player_info["bye"] = element["bye_weeks"].get("week", "N/A")
                                            
                                            # Ownership data
                                            if "ownership" in element:
                                                ownership = element["ownership"]
                                                player_info["owned_pct"] = ownership.get("ownership_percentage", 0)
                                                player_info["weekly_change"] = ownership.get("weekly_change", 0)
                                            
                                            # Injury status
                                            if "status" in element:
                                                player_info["injury_status"] = element["status"]
                                            if "status_full" in element:
                                                player_info["injury_detail"] = element["status_full"]
                                    
                                    if player_info.get("name"):
                                        players.append(player_info)
            
            result = {
                "league_key": league_key,
                "position": position or "all",
                "count": len(players),
                "players": players[:count]
            }
            
        elif name == "ff_get_optimal_lineup":
            # Get optimal lineup recommendations with Sleeper integration
            league_key = arguments.get("league_key")
            week = arguments.get("week", None)
            strategy = arguments.get("strategy", "balanced")
            
            # Get user's roster
            team_key = await get_user_team_key(league_key)
            
            if team_key:
                # Get roster data from Yahoo
                roster_data = await yahoo_api_call(f"team/{team_key}/roster")
                
                # Import and use lineup optimizer
                from src.lineup_optimizer import LineupOptimizer
                
                # Create optimizer instance
                optimizer = LineupOptimizer()
                
                # Parse roster
                players = await optimizer.parse_yahoo_roster(roster_data)
                
                # Enhance with external data (Sleeper, matchups, trending)
                players = await optimizer.enhance_with_external_data(players)
                
                # Optimize lineup
                optimization = optimizer.optimize_lineup(players, strategy)
                
                # Format starters for response
                starters_formatted = {}
                for pos, player in optimization["starters"].items():
                    starters_formatted[pos] = {
                        "name": player.name,
                        "tier": player.player_tier.upper() if player.player_tier else "UNKNOWN",
                        "team": player.team,
                        "opponent": player.opponent,
                        "matchup_score": player.matchup_score,
                        "matchup": player.matchup_description,
                        "composite_score": round(player.composite_score, 1),
                        "yahoo_proj": round(player.yahoo_projection, 1) if player.yahoo_projection else None,
                        "sleeper_proj": round(player.sleeper_projection, 1) if player.sleeper_projection else None,
                        "trending": f"{player.trending_score:,} adds" if player.trending_score > 0 else None
                    }
                
                # Format bench for response
                bench_formatted = []
                for player in optimization["bench"][:5]:  # Top 5 bench players
                    bench_formatted.append({
                        "name": player.name,
                        "position": player.position,
                        "opponent": player.opponent,
                        "composite_score": round(player.composite_score, 1),
                        "matchup_score": player.matchup_score
                    })
                
                result = {
                    "league_key": league_key,
                    "team_key": team_key,
                    "week": week or "current",
                    "strategy": strategy,
                    "optimal_lineup": starters_formatted,
                    "bench": bench_formatted,
                    "recommendations": optimization["recommendations"],
                    "analysis": {
                        "total_players": len(players),
                        "strategy_used": optimization["strategy_used"],
                        "data_sources": ["Yahoo projections", "Sleeper rankings", "Matchup analysis", "Trending data"]
                    }
                }
            else:
                result = {
                    "error": f"Could not find your team in league {league_key}"
                }
            
        elif name == "ff_refresh_token":
            # Refresh the Yahoo access token
            result = await refresh_yahoo_token()
            
        elif name == "ff_get_api_status":
            # Get API rate limit and cache status
            rate_status = rate_limiter.get_status()
            cache_stats = response_cache.get_stats()
            
            result = {
                "rate_limit": rate_status,
                "cache": cache_stats
            }
            
        elif name == "ff_clear_cache":
            # Clear cache
            pattern = arguments.get("pattern", None)
            await response_cache.clear(pattern)
            
            result = {
                "status": "success",
                "message": f"Cache cleared{f' for pattern: {pattern}' if pattern else ' completely'}"
            }
            
        elif name == "ff_get_draft_results":
            # Get draft results for all teams
            league_key = arguments.get("league_key")
            
            # Get all teams with draft info
            teams = await get_all_teams_info(league_key)
            
            if teams:
                # Get user's GUID to identify their team
                user_guid = os.getenv("YAHOO_GUID", "QQQ5VN577FJJ4GT2NLMJMIYEBU")
                
                # Mark user's team
                for team in teams:
                    # You can mark the user's team if needed
                    pass
                
                result = {
                    "league_key": league_key,
                    "total_teams": len(teams),
                    "draft_results": teams
                }
            else:
                result = {
                    "error": f"Could not retrieve draft results for league {league_key}"
                }
            
        elif name == "ff_get_waiver_wire":
            # Get waiver wire players
            league_key = arguments.get("league_key")
            position = arguments.get("position", "all")
            sort = arguments.get("sort", "rank")
            count = arguments.get("count", 20)
            
            players = await get_waiver_wire_players(league_key, position, sort, count)
            
            if players:
                result = {
                    "league_key": league_key,
                    "position": position,
                    "sort": sort,
                    "total_players": len(players),
                    "players": players
                }
            else:
                result = {
                    "league_key": league_key,
                    "message": "No available players found or error retrieving data"
                }
            
        elif name == "ff_get_draft_rankings":
            # Get pre-draft rankings
            league_key = arguments.get("league_key", None)
            position = arguments.get("position", "all")
            count = arguments.get("count", 50)
            
            players = await get_draft_rankings(league_key, position, count)
            
            if players:
                result = {
                    "position": position,
                    "total_players": len(players),
                    "rankings": players
                }
            else:
                result = {
                    "message": "Could not retrieve draft rankings"
                }
        
        elif name == "ff_get_draft_recommendation":
            # Get AI-powered draft recommendations
            if not DRAFT_AVAILABLE:
                result = {
                    "error": "Draft functionality not available. Please check module dependencies."
                }
            else:
                try:
                    league_key = arguments.get("league_key")
                    strategy = arguments.get("strategy", "balanced")
                    num_recommendations = arguments.get("num_recommendations", 10)
                    current_pick = arguments.get("current_pick")
                    
                    # Create simplified draft recommendation
                    result = await get_draft_recommendation_simple(
                        league_key, strategy, num_recommendations, current_pick
                    )
                except Exception as e:
                    result = {
                        "error": f"Draft recommendation failed: {str(e)}",
                        "available_tools": ["ff_get_draft_rankings", "ff_get_players"]
                    }
        
        elif name == "ff_analyze_draft_state":
            # Analyze current draft state
            if not DRAFT_AVAILABLE:
                result = {
                    "error": "Draft functionality not available. Please check module dependencies."
                }
            else:
                try:
                    league_key = arguments.get("league_key")
                    strategy = arguments.get("strategy", "balanced")
                    
                    # Create simplified draft state analysis
                    result = await analyze_draft_state_simple(league_key, strategy)
                except Exception as e:
                    result = {
                        "error": f"Draft analysis failed: {str(e)}",
                        "suggestion": "Try using ff_get_roster to check current team composition"
                    }
            
        elif name == "ff_analyze_reddit_sentiment":
            # Analyze Reddit sentiment for players
            players = arguments.get("players", [])
            time_window = arguments.get("time_window_hours", 48)
            
            if not players:
                result = {"error": "No players specified for sentiment analysis"}
            else:
                result = await analyze_reddit_sentiment(players, time_window)
        
        elif name == "ff_get_opponent_roster":
            # Get opponent roster for matchup analysis
            league_key = arguments.get("league_key")
            week = arguments.get("week")
            
            if not league_key:
                result = {"error": "League key is required"}
            else:
                try:
                    result = await get_opponent_roster_simple(league_key, week)
                except Exception as e:
                    result = {
                        "error": f"Failed to get opponent roster: {str(e)}",
                        "suggestion": "Check that the league key is valid and you have an active matchup"
                    }
        
        elif name == "ff_get_opponent_roster_comparison":
            # Get detailed roster comparison with opponent
            league_key = arguments.get("league_key")
            week = arguments.get("week")
            
            if not league_key:
                result = {"error": "League key is required"}
            else:
                try:
                    result = await get_opponent_roster_comparison_simple(league_key, week)
                except Exception as e:
                    result = {
                        "error": f"Failed to get roster comparison: {str(e)}",
                        "suggestion": "Check that the league key is valid and you have an active matchup"
                    }
        
        elif name == "ff_get_all_teams":
            # Get all teams in the league with their rosters
            league_key = arguments.get("league_key")
            
            if not league_key:
                result = {"error": "League key is required"}
            else:
                try:
                    result = await get_all_teams_with_rosters(league_key)
                except Exception as e:
                    result = {
                        "error": f"Failed to get all teams: {str(e)}",
                        "suggestion": "Check that the league key is valid"
                    }
        
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    except Exception as e:
        error_result = {
            "error": str(e),
            "tool": name,
            "arguments": arguments
        }
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def get_draft_recommendation_simple(league_key: str, strategy: str, num_recommendations: int, current_pick: Optional[int] = None) -> dict:
    """Simplified draft recommendation using available data."""
    try:
        # Get available players using existing waiver wire function
        available_players = await get_waiver_wire_players(league_key, count=100)
        draft_rankings = await get_draft_rankings(league_key, count=50)
        
        # Simple scoring based on rankings and availability
        recommendations = []
        
        # Create a quick lookup for available players
        available_names = {p.get("name", "").lower() for p in available_players}
        
        for player in draft_rankings:
            player_name = player.get("name", "").lower()
            if player_name in available_names:
                # Simple scoring based on strategy
                rank = player.get("rank", 999)
                base_score = max(0, 100 - rank)
                
                if strategy == "conservative":
                    # Prefer higher-ranked (safer) picks
                    score = base_score + (10 if rank <= 24 else 0)
                    reasoning = f"Rank #{rank}, conservative choice (proven player)"
                elif strategy == "aggressive": 
                    # Prefer potential breakouts (lower owned %)
                    owned_pct = next((p.get("owned_pct", 50) for p in available_players 
                                    if p.get("name", "").lower() == player_name), 50)
                    upside_bonus = max(0, 20 - (owned_pct / 5))  # Bonus for lower ownership
                    score = base_score + upside_bonus
                    reasoning = f"Rank #{rank}, high upside potential ({owned_pct}% owned)"
                else:  # balanced
                    score = base_score + (5 if rank <= 50 else 0)
                    reasoning = f"Rank #{rank}, balanced value pick"
                
                recommendations.append({
                    "player": player,
                    "score": score,
                    "reasoning": reasoning
                })
        
        # Sort by score and take top N
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        top_picks = recommendations[:num_recommendations]
        
        return {
            "status": "success", 
            "league_key": league_key,
            "strategy": strategy,
            "current_pick": current_pick,
            "recommendations": top_picks,
            "total_analyzed": len(recommendations),
            "insights": [
                f"Using {strategy} draft strategy",
                f"Analyzed {len(available_players)} available players",
                f"Cross-referenced with Yahoo rankings",
                "Recommendations prioritize available players only"
            ]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Draft recommendation failed: {str(e)}",
            "fallback": "Use ff_get_draft_rankings and ff_get_players for manual analysis"
        }


async def analyze_draft_state_simple(league_key: str, strategy: str) -> dict:
    """Simplified draft state analysis."""
    try:
        # Get current roster and league info
        roster_data = await yahoo_api_call(f"league/{league_key}/teams")
        leagues = await discover_leagues()
        league_info = leagues.get(league_key, {})
        
        # Analyze positional needs (simplified)
        user_team = await get_user_team_info(league_key)
        
        # Get current week to estimate draft progress
        current_week = league_info.get("current_week", 1)
        draft_phase = "pre_season" if current_week <= 1 else "mid_season"
        
        positional_needs = {
            "QB": "medium",  # Usually need 1-2
            "RB": "high",    # Need 3-5  
            "WR": "high",    # Need 3-5
            "TE": "medium",  # Need 1-2
            "K": "low",      # Stream position
            "DEF": "low"     # Stream position
        }
        
        strategic_advice = []
        if strategy == "conservative":
            strategic_advice.append("Focus on proven players with consistent production")
            strategic_advice.append("Avoid injury-prone or rookie players early")
        elif strategy == "aggressive":
            strategic_advice.append("Target high-upside players and breakout candidates")  
            strategic_advice.append("Consider reaching for players with league-winning potential")
        else:
            strategic_advice.append("Balance safety with upside potential")
            strategic_advice.append("Follow tier-based drafting approach")
        
        return {
            "status": "success",
            "league_key": league_key,
            "strategy": strategy,
            "analysis": {
                "draft_phase": draft_phase,
                "league_info": {
                    "name": league_info.get("name", "Unknown"),
                    "teams": league_info.get("num_teams", 12),
                    "scoring": league_info.get("scoring_type", "standard")
                },
                "positional_needs": positional_needs,
                "strategic_advice": strategic_advice,
                "your_team": user_team.get("team_name", "Unknown") if user_team else "Team info unavailable"
            },
            "recommendations": [
                "Use ff_get_draft_recommendation for specific player suggestions",
                "Monitor ff_get_players for available free agents",
                "Check ff_get_draft_rankings for current ADP data"
            ]
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "error": f"Draft analysis failed: {str(e)}",
            "basic_info": "Use ff_get_league_info for basic league details"
        }


async def get_opponent_roster_simple(league_key: str, week: int = None) -> dict:
    """Get opponent roster for matchup analysis."""
    try:
        # Get current week if not specified
        if week is None:
            leagues = await discover_leagues()
            league_info = leagues.get(league_key, {})
            week = league_info.get("current_week", 1)
        
        # Get matchup data to find opponent
        week_param = f";week={week}" if week else ""
        team_key = await get_user_team_key(league_key)
        
        if not team_key:
            return {
                "status": "error", 
                "error": "Could not find user team in this league",
                "suggestion": "Make sure you have access to this league"
            }
        
        # Get matchup information
        matchup_data = await yahoo_api_call(f"team/{team_key}/matchups{week_param}")
        
        # Extract opponent team key from matchup data
        opponent_team_key = None
        if "fantasy_content" in matchup_data and "team" in matchup_data["fantasy_content"]:
            team_data = matchup_data["fantasy_content"]["team"]
            
            # The team data is a list, check the second element for matchups
            if isinstance(team_data, list) and len(team_data) > 1:
                matchups_data = team_data[1]
                
                if "matchups" in matchups_data:
                    matchups = matchups_data["matchups"]
                    
                    # Get the matchup for the specified week (default to "0" for current week)
                    week_key = str(week - 1) if week else "0"  # Week 1 = index 0
                    
                    if week_key in matchups and "matchup" in matchups[week_key]:
                        matchup = matchups[week_key]["matchup"]
                        
                        # Look for teams in the matchup
                        if "0" in matchup and "teams" in matchup["0"]:
                            teams = matchup["0"]["teams"]
                            
                            # Check both team entries
                            for team_idx in ["0", "1"]:
                                if team_idx in teams and "team" in teams[team_idx]:
                                    team_info = teams[team_idx]["team"]
                                    
                                    # Extract team_key from the team data structure
                                    if isinstance(team_info, list) and len(team_info) > 0:
                                        team_details = team_info[0]
                                        if isinstance(team_details, list):
                                            for detail in team_details:
                                                if isinstance(detail, dict) and "team_key" in detail:
                                                    found_team_key = detail["team_key"]
                                                    # If this is not the user's team, it's the opponent
                                                    if found_team_key != team_key:
                                                        opponent_team_key = found_team_key
                                                        break
                                    
                                    if opponent_team_key:
                                        break
        
        if not opponent_team_key:
            return {
                "error": "Could not find opponent for this week",
                "suggestion": "Make sure you have an active matchup for the specified week",
                "debug_info": {
                    "league_key": league_key,
                    "week": week,
                    "team_key": team_key,
                    "matchup_data_keys": list(matchup_data.keys()) if matchup_data else [],
                    "fantasy_content_keys": list(matchup_data.get("fantasy_content", {}).keys()) if matchup_data else []
                }
            }
        
        # Get opponent roster
        opponent_roster_data = await yahoo_api_call(f"team/{opponent_team_key}/roster")
        
        # Parse opponent roster
        opponent_players = []
        if "fantasy_content" in opponent_roster_data and "team" in opponent_roster_data["fantasy_content"]:
            team_data = opponent_roster_data["fantasy_content"]["team"]
            
            # Extract team name from the team data structure
            opponent_team_name = "Unknown Opponent"
            if isinstance(team_data, list) and len(team_data) > 0:
                team_info = team_data[0]
                if isinstance(team_info, list):
                    for detail in team_info:
                        if isinstance(detail, dict) and "name" in detail:
                            opponent_team_name = detail["name"]
                            break
            
            # Parse roster data using the same logic as the working ff_get_roster tool
            # Look for roster data in the team array
            for item in team_data:
                if isinstance(item, dict) and "roster" in item:
                    roster_data = item["roster"]
                    # Roster data is typically in the "0" key
                    if "0" in roster_data and "players" in roster_data["0"]:
                        players = roster_data["0"]["players"]
                        
                        for player_id, player_data in players.items():
                            if player_id == "count":
                                continue
                            
                            player = player_data["player"]
                            
                            # Extract player details from the nested structure
                            if isinstance(player, list) and len(player) > 0:
                                player_details = player[0]
                                if isinstance(player_details, list):
                                    player_info = {}
                                    for detail in player_details:
                                        if isinstance(detail, dict):
                                            if "name" in detail:
                                                player_info["name"] = detail["name"]["full"]
                                            if "display_position" in detail:
                                                player_info["position"] = detail["display_position"]
                                            if "editorial_team_abbr" in detail:
                                                player_info["team"] = detail["editorial_team_abbr"]
                                            if "status" in detail:
                                                player_info["status"] = detail["status"]
                                    
                                    if player_info.get("name"):
                                        opponent_players.append(player_info)
                    break  # Found roster data, no need to continue
        else:
            opponent_team_name = "Unknown Opponent"
        
        return {
            "status": "success",
            "league_key": league_key,
            "week": week,
            "opponent_roster": {
                "team_name": opponent_team_name,
                "team_key": opponent_team_key,
                "players": opponent_players,
                "matchup_context": {
                    "week": week,
                    "opponent_team_key": opponent_team_key,
                    "matchup_status": "upcoming"
                }
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get opponent roster: {str(e)}",
            "suggestion": "Check that you have an active matchup for the specified week",
            "debug_info": {
                "exception": str(e),
                "league_key": league_key,
                "week": week
            }
        }


async def get_opponent_roster_comparison_simple(league_key: str, week: int = None) -> dict:
    """Get detailed roster comparison with opponent."""
    try:
        # Get both rosters
        # Get my roster using the same pattern as ff_get_roster
        team_key = await get_user_team_key(league_key)
        
        if not team_key:
            return {
                "status": "error",
                "error": "Could not find user team in this league",
                "suggestion": "Make sure you have access to this league"
            }
        my_roster_raw = await yahoo_api_call(f"team/{team_key}/roster")
        
        # Parse my roster
        my_roster = []
        team_name = "Your Team"
        team_data = my_roster_raw.get("fantasy_content", {}).get("team", [])
        
        for item in team_data:
            if isinstance(item, dict):
                if "name" in item:
                    team_name = item["name"]
                elif "roster" in item:
                    roster_data = item["roster"]
                    if "0" in roster_data and "players" in roster_data["0"]:
                        players = roster_data["0"]["players"]
                        for key in players:
                            if key != "count" and isinstance(players[key], dict):
                                if "player" in players[key]:
                                    player_array = players[key]["player"]
                                    
                                    # Extract player info from the nested structure (same as opponent roster)
                                    if isinstance(player_array, list) and len(player_array) > 0:
                                        player_details = player_array[0]
                                        if isinstance(player_details, list):
                                            player_info = {}
                                            for detail in player_details:
                                                if isinstance(detail, dict):
                                                    if "name" in detail and "full" in detail["name"]:
                                                        player_info["name"] = detail["name"]["full"]
                                                    if "display_position" in detail:
                                                        player_info["position"] = detail["display_position"]
                                            
                                            if player_info.get("name"):
                                                my_roster.append(player_info)
        
        my_roster_data = {
            "team_name": team_name,
            "roster": my_roster
        }
        
        opponent_data = await get_opponent_roster_simple(league_key, week)
        
        if opponent_data.get("status") == "error":
            return opponent_data
        
        opponent_roster = opponent_data["opponent_roster"]
        
        # Simple position-by-position comparison
        position_comparison = {}
        my_positions = {}
        opponent_positions = {}
        
        # Group my players by position
        for player in my_roster_data.get("roster", []):
            pos = player.get("position", "UNKNOWN")
            if pos not in my_positions:
                my_positions[pos] = []
            my_positions[pos].append(player)
        
        # Group opponent players by position
        for player in opponent_roster["players"]:
            pos = player.get("position", "UNKNOWN")
            if pos not in opponent_positions:
                opponent_positions[pos] = []
            opponent_positions[pos].append(player)
        
        # Compare positions
        all_positions = set(list(my_positions.keys()) + list(opponent_positions.keys()))
        for pos in all_positions:
            my_count = len(my_positions.get(pos, []))
            opp_count = len(opponent_positions.get(pos, []))
            
            # Simple strength assessment based on player count and names
            if my_count > opp_count:
                advantage = "strong"
            elif my_count < opp_count:
                advantage = "weak" 
            else:
                advantage = "neutral"
            
            position_comparison[pos] = {
                "my_player_count": my_count,
                "opponent_player_count": opp_count,
                "advantage": advantage,
                "my_players": [p.get("name", "Unknown") for p in my_positions.get(pos, [])],
                "opponent_players": [p.get("name", "Unknown") for p in opponent_positions.get(pos, [])]
            }
        
        # Generate basic recommendations
        recommendations = []
        weak_positions = [pos for pos, data in position_comparison.items() 
                         if data["advantage"] == "weak"]
        strong_positions = [pos for pos, data in position_comparison.items() 
                          if data["advantage"] == "strong"]
        
        if weak_positions:
            recommendations.append(f"Consider strengthening these positions: {', '.join(weak_positions)}")
        if strong_positions:
            recommendations.append(f"Your advantages are at: {', '.join(strong_positions)}")
        
        recommendations.append("Use ff_get_waiver_wire to find available upgrades")
        recommendations.append("Monitor player news and injuries before game time")
        
        return {
            "status": "success",
            "league_key": league_key,
            "week": week,
            "my_roster": {
                "team_name": my_roster_data.get("team_name", "Your Team"),
                "player_count": len(my_roster_data.get("roster", [])),
                "players": my_roster_data.get("roster", [])
            },
            "opponent_roster": opponent_roster,
            "matchup_insights": {
                "position_comparison": position_comparison,
                "recommendations": recommendations,
                "summary": f"Facing {opponent_roster['team_name']} in Week {week}"
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to compare rosters: {str(e)}",
            "suggestion": "Try using ff_get_roster and ff_get_opponent_roster separately"
        }


async def get_all_teams_with_rosters(league_key: str) -> dict:
    """Get all teams in the league with their rosters for comparison."""
    try:
        # Get all teams in the league
        data = await yahoo_api_call(f"league/{league_key}/teams")
        
        teams_info = []
        league = data.get("fantasy_content", {}).get("league", [])
        
        if len(league) > 1 and isinstance(league[1], dict) and "teams" in league[1]:
            teams = league[1]["teams"]
            
            for key in teams:
                if key != "count" and isinstance(teams[key], dict):
                    if "team" in teams[key]:
                        team_array = teams[key]["team"]
                        
                        if isinstance(team_array, list) and len(team_array) > 0:
                            team_data = team_array[0]
                            
                            if isinstance(team_data, list):
                                team_key = None
                                team_name = None
                                is_users_team = False
                                draft_grade = None
                                draft_position = None
                                
                                # Parse team info
                                for element in team_data:
                                    if isinstance(element, dict):
                                        if "team_key" in element:
                                            team_key = element["team_key"]
                                        if "name" in element:
                                            team_name = element["name"]
                                        if "draft_grade" in element:
                                            draft_grade = element["draft_grade"]
                                        if "draft_position" in element:
                                            draft_position = element["draft_position"]
                                        if "is_owned_by_current_login" in element and element["is_owned_by_current_login"] == 1:
                                            is_users_team = True
                                
                                if team_key and team_name:
                                    # Get roster for this team
                                    try:
                                        roster_data = await yahoo_api_call(f"team/{team_key}/roster")
                                        roster = []
                                        
                                        team = roster_data.get("fantasy_content", {}).get("team", [])
                                        if len(team) > 1 and isinstance(team[1], dict) and "roster" in team[1]:
                                            roster_info = team[1]["roster"]
                                            if "0" in roster_info and "players" in roster_info["0"]:
                                                players = roster_info["0"]["players"]
                                                
                                                for player_key in players:
                                                    if player_key != "count" and isinstance(players[player_key], dict):
                                                        if "player" in players[player_key]:
                                                            player_array = players[player_key]["player"]
                                                            if isinstance(player_array, list) and len(player_array) > 0:
                                                                player_data = player_array[0]
                                                                
                                                                if isinstance(player_data, list):
                                                                    player_info = {}
                                                                    
                                                                    for element in player_data:
                                                                        if isinstance(element, dict):
                                                                            if "name" in element:
                                                                                name_val = element["name"]
                                                                                if isinstance(name_val, dict):
                                                                                    player_info["name"] = name_val.get("full") or name_val.get("first")
                                                                                elif isinstance(name_val, str):
                                                                                    player_info["name"] = name_val
                                                                            if "selected_position" in element:
                                                                                sel = element["selected_position"]
                                                                                if isinstance(sel, list) and len(sel) > 0:
                                                                                    if isinstance(sel[0], dict):
                                                                                        player_info["position"] = sel[0].get("position") or sel[0].get("position_type")
                                                                                    else:
                                                                                        player_info["position"] = str(sel[0])
                                                                                elif isinstance(sel, dict):
                                                                                    player_info["position"] = sel.get("position") or sel.get("position_type")
                                                                            elif "display_position" in element:
                                                                                player_info["position"] = element["display_position"]
                                                                            elif "position" in element:
                                                                                player_info["position"] = element["position"]
                                                                            if "status" in element:
                                                                                player_info["status"] = element.get("status", "OK")
                                                                            elif "status_full" in element:
                                                                                player_info["status"] = element.get("status_full", "OK")
                                                                    
                                                                    if player_info.get("name"):
                                                                        roster.append(player_info)
                                        
                                        teams_info.append({
                                            "team_key": team_key,
                                            "team_name": team_name,
                                            "draft_position": draft_position,
                                            "draft_grade": draft_grade,
                                            "is_users_team": is_users_team,
                                            "roster": roster,
                                            "player_count": len(roster)
                                        })
                                        
                                    except Exception as e:
                                        # If we can't get roster, still include team info
                                        teams_info.append({
                                            "team_key": team_key,
                                            "team_name": team_name,
                                            "draft_position": draft_position,
                                            "draft_grade": draft_grade,
                                            "is_users_team": is_users_team,
                                            "roster": [],
                                            "player_count": 0,
                                            "roster_error": str(e)
                                        })
        
        return {
            "status": "success",
            "league_key": league_key,
            "total_teams": len(teams_info),
            "teams": teams_info
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get all teams: {str(e)}",
            "suggestion": "Check that the league key is valid"
        }


async def main():
    """Run the MCP server."""
    # Use stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())