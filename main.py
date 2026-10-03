import asyncio
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from browser_manager import BrowserManager
from agent import BrowserAgent
from history_logger import HistoryLogger

load_dotenv()
console = Console()

def print_header():
    header = Text("BROWSER AGENT", justify="center", style="bold cyan")
    console.print(Panel(header, width=60, border_style="cyan"))

def print_status(goal: str, url: str, status: str = "RUNNING"):
    content = f"[bold white]Goal:[/bold white]\n{goal}\n\n"
    content += f"[bold white]Current URL:[/bold white]\n{url}\n\n"
    
    status_color = "green" if status == "SUCCESS" else "red" if status == "FAILED" else "yellow"
    content += f"[bold white]Status:[/bold white]\n[{status_color}]{status}[/{status_color}]"
    console.print(content)
    console.print("-" * 60)

def print_agent_thought(command: dict):
    cmd_type = command.get('command')
    desc = command.get('description', '')
    target = command.get('selector') or command.get('url') or command.get('text') or command.get('value') or ''
    
    console.print("[bold magenta][Agent][/bold magenta]")
    if desc:
        console.print(f"Thought: {desc}")
        
    console.print("\n[bold blue][Command][/bold blue]")
    console.print(cmd_type)
    
    if target:
        console.print("\n[bold blue][Target][/bold blue]")
        console.print(target)

def print_action_result(result: str):
    console.print("\n[bold green][Action][/bold green]")
    console.print(result)
    console.print("-" * 60)

def print_browser_update(elements_count: int):
    console.print("[bold cyan][Browser][/bold cyan]")
    console.print("Page loaded/changed.")
    console.print("\n[bold cyan][Scraper][/bold cyan]")
    console.print(f"Extracted {elements_count} interactive elements.")
    console.print("\n[bold magenta][Agent][/bold magenta]")
    console.print("Analyzing the new page...")
    console.print("-" * 60)

async def main():
    print_header()
    
    goal = console.input("[bold green]Enter Goal: [/bold green]")
    start_url = console.input("[bold green]Enter Starting URL: [/bold green]")
    
    console.print("\n[yellow]Initializing Browser Agent...[/yellow]\n")
    
    browser_manager = BrowserManager()
    try:
        agent = BrowserAgent()
    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
        
    logger = HistoryLogger()
    
    await browser_manager.start(headless=False)
    
    try:
        # Initial navigation
        await browser_manager.execute_command({"command": "navigate", "url": start_url})
        step = 1
        
        while True:
            # Scrape page
            page_info = await browser_manager.scrape_page()
            elements_count = len(page_info.links) + len(page_info.buttons) + len(page_info.inputs)
            
            print_status(goal, page_info.url, "RUNNING")
            print_browser_update(elements_count)
            
            # Send to LLM
            history_summary = logger.get_history_summary()
            command = agent.determine_next_action(goal, page_info, history_summary)
            
            print_agent_thought(command)
            
            # Check finish condition
            cmd_type = command.get("command")
            if cmd_type == "finish":
                status = command.get("status")
                msg = command.get("message")
                logger.log_step(step, command, page_info.url)
                
                final_state = "SUCCESS" if msg == "banana" else "FAILED"
                print_action_result(f"Agent decided to finish with status: {status} ({msg})")
                print_status(goal, page_info.url, final_state)
                break
                
            # Execute command
            result = await browser_manager.execute_command(command)
            print_action_result(result)
            
            # Log step
            logger.log_step(step, command, page_info.url)
            step += 1
            
            await asyncio.sleep(2) # Brief pause for visibility and avoiding rate limits

    except Exception as e:
        console.print(f"[bold red]Critical Error: {str(e)}[/bold red]")
    finally:
        await browser_manager.close()
        console.print("\n[bold cyan]Browser closed. Session ended.[/bold cyan]")

if __name__ == "__main__":
    asyncio.run(main())
