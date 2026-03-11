# simple_cricket.py

import random

class Player:
    def __init__(self, name):
        self.name = name
        self.runs = 0
        self.balls = 0

class CricketMatch:
    def __init__(self, players, overs=5):
        self.players = [Player(name) for name in players]
        self.overs = overs
        self.current_over = 0
        self.current_ball = 0
        self.total_runs = 0
        self.wickets = 0
        self.batsman_index = 0
        self.max_wickets = len(players) - 1

    def ball_outcome(self):
        """Random outcome of a ball following cricket rules"""
        outcome = random.choices(
            population=["0","1","2","3","4","6","W"],
            weights=[0.2,0.3,0.15,0.05,0.2,0.05,0.05],
            k=1
        )[0]
        return outcome

    def play_ball(self):
        batsman = self.players[self.batsman_index]
        outcome = self.ball_outcome()
        print(f"Ball {self.current_over+1}.{self.current_ball+1}: {batsman.name} -> {outcome}")
        if outcome == "W":
            self.wickets += 1
            print(f"{batsman.name} is OUT!")
            if self.wickets >= self.max_wickets:
                print("All out!")
                return False
            else:
                self.batsman_index += 1
        else:
            runs = int(outcome)
            batsman.runs += runs
            self.total_runs += runs
        self.current_ball += 1
        if self.current_ball >= 6:
            self.current_over += 1
            self.current_ball = 0
            print(f"End of Over {self.current_over}")
        return True

    def start_match(self):
        print("Starting Cricket Match!")
        while self.current_over < self.overs and self.wickets < self.max_wickets:
            if not self.play_ball():
                break
        self.show_scorecard()

    def show_scorecard(self):
        print("\n--- Match Ended ---")
        print(f"Total Runs: {self.total_runs}")
        print(f"Wickets Lost: {self.wickets}")
        print("Player Scores:")
        for player in self.players:
            print(f"{player.name}: {player.runs} ({player.balls} balls)")

# ===== Example Usage =====
if __name__ == "__main__":
    player_names = ["Player1", "Player2", "Player3", "Player4", "Player5"]
    match = CricketMatch(player_names, overs=5)
    match.start_match()
