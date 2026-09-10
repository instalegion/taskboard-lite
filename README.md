# TaskBoard Lite

Ένα αποδοτικό σύστημα διαχείρισης εργασιών Kanban-style (To Do / In Progress / Done) εμπνευσμένο από τις αρχές του Scrum για διαχείριση προσωπικών έργων.

## Τεχνολογικό Stack
- **Backend:** Python (FastAPI)
- **Database:** SQLite μέσω SQLAlchemy ORM
- **Authentication:** JWT (JSON Web Tokens) & SHA-256 password hashing
- **Caching:** In-Memory Cache (σε επίπεδο εφαρμογής για τα στατιστικά boards)
- **Frontend:** HTML5, Modern JavaScript, Tailwind CSS (μέσω CDN)

## Οδηγίες Εγκατάστασης & Εκτέλεσης

1. Δημιουργία και ενεργοποίηση virtual environment:
python -m venv venv
.\venv\Scripts\Activate

2. Εγκατάσταση απαραίτητων πακέτων:
pip install fastapi "uvicorn[standard]" sqlalchemy pyjwt python-multipart

3. Εκκίνηση του Server:
python -m uvicorn main:app --reload

4. Πρόσβαση στις υπηρεσίες:
- Web App: http://127.0.0.1:8000
- Αυτόματη Τεκμηρίωση API (Swagger UI): http://127.0.0.1:8000/docs
- Εναλλακτική Τεκμηρίωση (Redoc): http://127.0.0.1:8000/redoc

## Endpoints API

### Auth
- `POST /auth/register` : Εγγραφή νέου χρήστη
- `POST /auth/login` : Σύνδεση και έκδοση JWT Bearer token

### Boards
- `GET /boards` : Λήψη λίστας των boards του χρήστη
- `POST /boards` : Δημιουργία νέου board
- `DELETE /boards/{board_id}` : Διαγραφή πίνακα και cascade διαγραφή των συνδεδεμένων tasks
- `PUT /boards/{board_id}` : Ενημέρωση τίτλου πίνακα

### Tasks
- `GET /boards/{board_id}/tasks` : Λήψη όλων των tasks ενός board
- `POST /boards/{board_id}/tasks` : Δημιουργία νέου task
- `PUT /tasks/{task_id}` : Ενημέρωση κατάστασης ή στοιχείων task
- `DELETE /tasks/{task_id}` : Διαγραφή task

### Statistics & Cache
- `GET /boards/{board_id}/stats` : Επιστροφή συγκεντρωτικών στοιχείων (To Do, In Progress, Done) με χρήση In-Memory Cache (TTL: 60s)