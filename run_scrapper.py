import requests
from bs4 import BeautifulSoup
import sqlite3


class Fighter:
    def __init__(
        self,
        full_name=None,
        total=0,
        wins=0,
        wins_by_knockout=0,
        wins_by_submission=0,
        wins_by_decision=0,
        wins_by_disqualification=0,
        losses=0,
        loss_by_knockout=0,
        loss_by_submission=0,
        loss_by_decision=0,
        loss_by_disqualification=0,
        no_contests=0
        ):
        self.full_name = full_name
        self.total = total
        self.wins = wins
        self.wins_by_knockout = wins_by_knockout
        self.wins_by_submission = wins_by_submission
        self.wins_by_decision = wins_by_decision
        self.wins_by_disqualification = wins_by_disqualification
        self.losses = losses
        self.loss_by_knockout = loss_by_knockout
        self.loss_by_submission = loss_by_submission
        self.loss_by_decision = loss_by_decision
        self.loss_by_disqualification = loss_by_disqualification
        self.no_contests = no_contests


class WikipediaScraper:
    BASE_URL = "https://en.wikipedia.org/wiki/"

    def fetch_page(self, fighter_name):
        url = f"{self.BASE_URL}{fighter_name}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching page for {fighter_name}: {response.status_code}")
            return None
        return BeautifulSoup(response.text, "html.parser")

    def parse_fighter_info(self, soup: BeautifulSoup) -> Fighter | None:
        infobox = soup.find("table", {"class": "infobox"})
        if not infobox:
            print("Infobox not found.")
            return None

        data = Fighter()

        for row in infobox.find_all("tr"):
            header = row.find("th", attrs={"class": "infobox-above"})
            if header:
                data.full_name = header.get_text(strip=True)

        mma_record_header = infobox.find(
            lambda tag: tag.name == "th" and "Mixed martial arts" in tag.get_text(strip=True)
        )

        if not mma_record_header:
            return data

        rows = mma_record_header.find_parent("tr").find_next_siblings("tr")
        current_section = None

        for row in rows:
            header = row.find("th", attrs={"class": "infobox-label"})
            cell = row.find("td", attrs={"class": "infobox-data"})

            if not (header and cell):
                break

            key = header.get_text(strip=True)
            value = int(cell.get_text(strip=True))

            if key == "Wins":
                current_section = "wins"
                data.wins = value
            elif key == "Losses":
                current_section = "losses"
                data.losses = value
            elif key == "Total":
                data.total = value
            elif key == "No\xa0contests":
                data.no_contests = value

            elif key == "By\xa0knockout":
                if current_section == "wins":
                    data.wins_by_knockout = value
                elif current_section == "losses":
                    data.loss_by_knockout = value
            elif key == "By\xa0submission":
                if current_section == "wins":
                    data.wins_by_submission = value
                elif current_section == "losses":
                    data.loss_by_submission = value
            elif key == "By\xa0decision":
                if current_section == "wins":
                    data.wins_by_decision = value
                elif current_section == "losses":
                    data.loss_by_decision = value
            elif key == "By\xa0disqualification":
                if current_section == "wins":
                    data.wins_by_disqualification = value
                elif current_section == "losses":
                    data.loss_by_disqualification = value

        return data


class FighterDatabase:
    def __init__(self, db_name="mma_fighters.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS fighters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            total INT,
            wins INT,
            wins_by_knockout INT,
            wins_by_submission INT,
            wins_by_decision INT,
            wins_by_disqualification INT,
            losses INT,
            loss_by_knockout INT,
            loss_by_submission INT,
            loss_by_decision INT,
            loss_by_disqualification INT,
            no_contests INT
        )
        """)
        self.conn.commit()
    
    def check_fighter_exists(self, fighter: Fighter):
        self.cursor.execute("SELECT id FROM fighters WHERE full_name = ?", (fighter.full_name,))
        result = self.cursor.fetchone()
        return result is not None

    def save_or_update_fighter(self, fighter: Fighter):
        if self.check_fighter_exists(fighter):
            self.cursor.execute("""
            UPDATE fighters
            SET 
                total = ?, wins = ?, wins_by_knockout = ?, wins_by_submission = ?, wins_by_decision = ?, wins_by_disqualification = ?,
                losses = ?, loss_by_knockout = ?, loss_by_submission = ?, loss_by_decision = ?, loss_by_disqualification = ?,
                no_contests = ?
            WHERE full_name = ?
            """, (
                fighter.total,
                fighter.wins, fighter.wins_by_knockout, fighter.wins_by_submission, fighter.wins_by_decision, fighter.wins_by_disqualification,
                fighter.losses, fighter.loss_by_knockout, fighter.loss_by_submission, fighter.loss_by_decision, fighter.loss_by_disqualification,
                fighter.no_contests,
                fighter.full_name
            ))
            print(f"<< {fighter.full_name} >> info updated in the database.")
        else:
            self.cursor.execute("""
            INSERT INTO fighters (
                full_name, total, wins, wins_by_knockout, wins_by_submission, wins_by_decision, wins_by_disqualification,
                losses, loss_by_knockout, loss_by_submission, loss_by_decision, loss_by_disqualification,
                no_contests
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fighter.full_name, fighter.total,
                fighter.wins, fighter.wins_by_knockout, fighter.wins_by_submission, fighter.wins_by_decision, fighter.wins_by_disqualification,
                fighter.losses, fighter.loss_by_knockout, fighter.loss_by_submission, fighter.loss_by_decision, fighter.loss_by_disqualification,
                fighter.no_contests
            ))
            print(f"<< {fighter.full_name} >> info added to the database.")

        self.conn.commit()

    def close(self):
        self.conn.close()


fighters = [
    "Khabib_Nurmagomedov",
    "Conor_McGregor",
    "Islam_Makhachev",
    "Khamzat_Chimaev",
    "Amanda_Nunes",
    "Jon_Jones",
    "Dustin_Poirier",
]

scraper = WikipediaScraper()
db = FighterDatabase()

for fighter_name in fighters:
    soup = scraper.fetch_page(fighter_name)
    if soup:
        fighter_data = scraper.parse_fighter_info(soup)
        if fighter_data:
            db.save_or_update_fighter(fighter_data)

db.close()
