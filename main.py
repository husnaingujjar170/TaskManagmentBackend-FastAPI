import json
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware  # Import CORSMiddleware
from firebase_utils import verify_token, get_user
from firebase_admin import auth, firestore
import datetime
from config import PORT, API_TITLE, API_VERSION
from pydantic import BaseModel  # Import BaseModel for request body validation
from typing import Optional  # Import Optional for Pydantic

app = FastAPI(title=API_TITLE, version=API_VERSION)
db = firestore.client()

# --- ADD/UPDATE THIS CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local Vite dev server
        "https://reactfastapi-pi.vercel.app"  # Your deployed frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*", "id-token"],  # Allow all headers, including custom ones
)
# --- END CORS CONFIGURATION ---

# Pydantic models for request bodies
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    completed: Optional[bool] = False

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class UserSignup(BaseModel):
    email: str
    password: str
    username: str

class UserSignin(BaseModel):
    email: str
    password: str

# Test route - public
@app.get("/")
async def root():
    return {"message": "Welcome to the Task Management API"}

# Protected route - requires valid Firebase token
@app.get("/users/me")
async def read_users_me(id_token: str = Header(...)):
    decoded_token = verify_token(id_token)
    uid = decoded_token['uid']
    user = get_user(uid)
    return user

# User registration
@app.post("/auth/signup")
async def signup(user_data: UserSignup):  # Use Pydantic model for request body
    try:
        user = auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.username
        )

        # Create user profile in Firestore
        user_ref = db.collection('users').document(user.uid)
        user_ref.set({
            'email': user_data.email,
            'username': user_data.username,
            'createdAt': datetime.datetime.now(),
            'updatedAt': datetime.datetime.now()
        })

        return {
            "message": "User created successfully",
            "user_id": user.uid,
            "email": user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error creating user: " + str(e)
        )

# User login (password verification should happen on frontend)
@app.post("/auth/signin")
async def signin(user_data: UserSignin):  # Use Pydantic model for request body
    try:
        # In a real app, you'd verify password on the frontend using Firebase client SDK.
        # This backend endpoint primarily serves to confirm user existence and potentially
        # perform backend-specific login actions if needed.
        user = auth.get_user_by_email(user_data.email)
        return {"message": "Signin successful", "user_id": user.uid}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

# Create a task
@app.post("/tasks/")
async def create_task(task_data: TaskCreate, id_token: str = Header(...)):  # Use Pydantic model
    decoded_token = verify_token(id_token)
    uid = decoded_token['uid']

    task_dict = task_data.dict()  # Convert Pydantic model to dict
    task_dict['userId'] = uid
    task_dict['createdAt'] = datetime.datetime.now()
    task_dict['completed'] = task_data.completed  # Ensure completed is set from model

    # Add task to Firestore
    doc_ref = db.collection('tasks').document()  # Create a new document reference
    doc_ref.set(task_dict)  # Set the data to the new document

    return {"message": "Task created successfully", "taskId": doc_ref.id}  # Return the generated ID

# Get all tasks for the user
@app.get("/tasks/")
async def get_tasks(id_token: str = Header(...)):
    decoded_token = verify_token(id_token)
    uid = decoded_token['uid']

    tasks_ref = db.collection('tasks').where('userId', '==', uid)
    tasks = []
    for doc in tasks_ref.stream():
        task_data = doc.to_dict()
        task_data['id'] = doc.id  # Include document ID
        tasks.append(task_data)

    return {"tasks": tasks}

# Update a task
@app.put("/tasks/{task_id}")
async def update_task(task_id: str, updated_data: TaskUpdate, id_token: str = Header(...)):  # Use Pydantic model
    decoded_token = verify_token(id_token)
    uid = decoded_token['uid']

    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()

    if not task.exists:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.get('userId') != uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this task")

    # Update only provided fields
    update_dict = updated_data.dict(exclude_unset=True)  # Only include fields that were set
    task_ref.update(update_dict)
    return {"message": "Task updated successfully"}

# Delete a task
@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str, id_token: str = Header(...)):
    decoded_token = verify_token(id_token)
    uid = decoded_token['uid']

    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()

    if not task.exists:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.get('userId') != uid:
        raise HTTPException(status_code=403, detail="Not authorized to delete this task")

    task_ref.delete()
    return {"message": "Task deleted successfully"}

# Toggle task completion
@app.patch("/tasks/{task_id}")
async def toggle_task_complete(task_id: str, id_token: str = Header(...)):
    decoded_token = verify_token(id_token)
    uid = decoded_token['uid']

    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()

    if not task.exists:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.get('userId') != uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this task")

    # FIX: Correct way to get 'completed' with default
    current_completed = task.get('completed')
    if current_completed is None:
        current_completed = False
    task_ref.update({'completed': not current_completed})
    return {"message": "Task completion toggled successfully"}

def load_tasks(filename="tasks.json"):
    """Loads tasks from a JSON file."""
    try:
        with open(filename, 'r') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        tasks = []
    return tasks

def save_tasks(tasks, filename="tasks.json"):
    """Saves tasks to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(tasks, f, indent=4)

def add_task(tasks, description):
    """Adds a new task to the list."""
    task = {
        'id': len(tasks) + 1,
        'description': description,
        'completed': False
    }
    tasks.append(task)
    return tasks

def list_tasks(tasks):
    """Lists all tasks with their IDs and completion status."""
    if not tasks:
        print("No tasks found.")
        return

    for task in tasks:
        status = "✓" if task['completed'] else " "
        print(f"[{task['id']}] [{status}] {task['description']}")

def toggle_task_complete_old(tasks, task_id):
    """Toggles the completion status of a task."""
    try:
        task_id = int(task_id)
        for task in tasks:
            if task['id'] == task_id:
                current_completed = task.get('completed', default=False)
                task['completed'] = not current_completed
                print(f"Task {task_id} marked as {'completed' if task['completed'] else 'incomplete'}.")
                return tasks
        print(f"Task with ID {task_id} not found.")
    except ValueError:
        print("Invalid task ID. Please enter a number.")
    return tasks

def delete_task_old(tasks, task_id):
    """Deletes a task from the list."""
    try:
        task_id = int(task_id)
        original_length = len(tasks)
        tasks = [task for task in tasks if task['id'] != task_id]
        if len(tasks) < original_length:
            # Renumber the tasks to maintain sequential IDs
            for i, task in enumerate(tasks):
                task['id'] = i + 1
            print(f"Task {task_id} deleted.")
        else:
            print(f"Task with ID {task_id} not found.")
    except ValueError:
        print("Invalid task ID. Please enter a number.")
    return tasks

def main():
    """Main function to handle user input and task management."""
    tasks = load_tasks()

    while True:
        print("\nOptions:")
        print("1. Add task")
        print("2. List tasks")
        print("3. Toggle task completion")
        print("4. Delete task")
        print("5. Save and quit")

        choice = input("Enter your choice: ")

        if choice == '1':
            description = input("Enter task description: ")
            tasks = add_task(tasks, description)
        elif choice == '2':
            list_tasks(tasks)
        elif choice == '3':
            task_id = input("Enter task ID to toggle: ")
            tasks = toggle_task_complete_old(tasks, task_id)
        elif choice == '4':
            task_id = input("Enter task ID to delete: ")
            tasks = delete_task_old(tasks, task_id)
        elif choice == '5':
            save_tasks(tasks)
            print("Tasks saved. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
