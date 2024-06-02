import os
import openai
import speech_recognition as sr
import pyautogui
from PIL import Image
import base64
import requests
import threading
import time
from pydub import AudioSegment
from pydub.playback import play
import customtkinter as ctk
from tkinter import messagebox, END, BOTH, Text
from code_executor import process_response
import cv2

# Set up OpenAI API key
openai.api_key = ''

# Global flags to control the assistant
assistant_running = True
audio_input = False
vision_input = False
audio_output = False
stop_audio = False
camera_input = False

# Memory for storing conversation history
conversation_history = []

# Function to capture voice input
def get_voice_input():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        print("Recognizing...")
        query = recognizer.recognize_google(audio, language='en-US')
        print(f"User said: {query}\n")
    except Exception as e:
        print(e)
        return "Sorry, I did not understand that."
    return query

# Function to convert text to speech using OpenAI API
def speak(text):
    global stop_audio
    stop_audio = False

    # Split text into smaller chunks
    lines = text.split('. ')
    
    audio_segments = []
    for line in lines:
        if stop_audio:
            break
        headers = {
            "Authorization": f"Bearer {openai.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "tts-1",
            "input": line,
            "voice": "alloy"
        }
        response = requests.post("https://api.openai.com/v1/audio/speech", headers=headers, json=payload)
        
        # Save the audio file
        with open("response.mp3", "wb") as audio_file:
            audio_file.write(response.content)
        
        # Load the audio file using pydub and append to the list
        audio = AudioSegment.from_mp3("response.mp3")
        audio_segments.append(audio)
    
    if not stop_audio:
        # Concatenate all audio segments and play
        combined_audio = sum(audio_segments)
        play(combined_audio)

# Function to stop speech
def stop_speech():
    global stop_audio
    stop_audio = True

# Function to capture the most recent screenshot
def capture_screenshot():
    screenshot = pyautogui.screenshot()
    screenshot_path = "recent_screenshot.png"
    screenshot.save(screenshot_path)
    return screenshot_path

# Function to encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to interact with OpenAI's API
def get_openai_response(prompt, image_path=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}"
    }
    content = [{"type": "text", "text": prompt}]
    if image_path:
        base64_image = encode_image(image_path)
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "max_tokens": 300
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    return response.json()['choices'][0]['message']['content']

def assistant_loop():
    global assistant_running, audio_input, vision_input, camera_input
    while assistant_running:
        if audio_input:
            query = get_voice_input()
            if query:
                process_query(query)
        time.sleep(1)  # Small delay to prevent overwhelming the system

def handle_command(command):
    global audio_input, vision_input, audio_output, camera_input
    if command == '/ai':
        audio_input = not audio_input
        print(f"Audio input {'enabled' if audio_input else 'disabled'}")
    elif command == '/v':
        vision_input = not vision_input
        print(f"Vision input {'enabled' if vision_input else 'disabled'}")
    elif command == '/au':
        audio_output = not audio_output
        print(f"Audio output {'enabled' if audio_output else 'disabled'}")
    elif command == '/c':
        camera_input = not camera_input
        print(f"Camera input {'enabled' if camera_input else 'disabled'}")
        if camera_input:
            show_camera_window()
        else:
            hide_camera_window()
    else:
        print("Unknown command. Available commands: /ai, /v, /au, /c")

def toggle_audio_input():
    handle_command('/ai')
    update_button_style(btn1, audio_input)

def toggle_vision_input():
    handle_command('/v')
    update_button_style(btn2, vision_input)

def toggle_audio_output():
    handle_command('/au')
    update_button_style(btn3, audio_output)

def toggle_camera_input():
    handle_command('/c')
    update_button_style(btn4, camera_input)

def quit_app():
    global assistant_running
    assistant_running = False
    root.destroy()

def send_query(event=None):
    query = input_box.get("1.0", END).strip()
    if query:
        input_box.delete("1.0", END)
        process_query(query)
    else:
        # If the input box is empty and Enter is pressed twice, send the query
        if event and event.widget.get("1.0", END).strip() == "":
            process_query("")

def process_query(query):
    global conversation_history
    conversation_history.append(f"User: {query}")
    output_box.insert(END, f"\n\nUser: {query}\n", "user")
    if camera_input:
        screenshot_path = capture_camera_frame()
    elif vision_input:
        screenshot_path = capture_screenshot()
    else:
        screenshot_path = None
    prompt = f"User said: {query}. Here is the conversation history: {conversation_history}"
    if screenshot_path:
        prompt += " [if there is an image act like you can see it]"
    response = get_openai_response(prompt, screenshot_path)
    processed_response = process_response(response)

    conversation_history.append(f"AI: {processed_response}")
    output_box.insert(END, f"\nAI: {processed_response}\n", "ai")
    if audio_output:
        threading.Thread(target=speak, args=(processed_response,)).start()
    output_box.see(END)  # Auto-scroll to the end

def update_button_style(button, active):
    if active:
        button.configure(fg_color="green", text_color="black")
    else:
        button.configure(fg_color="black", text_color="green")

def show_camera_window():
    global camera_window, camera
    camera_window = ctk.CTkToplevel(root)
    camera_window.title("Camera Feed")
    camera_window.geometry("640x480")
    camera_label = ctk.CTkLabel(camera_window)
    camera_label.pack()
    camera = cv2.VideoCapture(0)
    update_camera_frame(camera_label)

def hide_camera_window():
    global camera_window, camera
    if camera_window:
        camera_window.destroy()
        camera_window = None
    if camera:
        camera.release()
        camera = None

def update_camera_frame(label):
    global camera_window, camera
    if camera_window and camera:
        ret, frame = camera.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img_tk = ctk.CTkImage(img, size=(640, 480))
            label.configure(image=img_tk)
        camera_window.after(10, update_camera_frame, label)

def capture_camera_frame():
    global camera
    if camera:
        ret, frame = camera.read()
        if ret:
            camera_frame_path = "camera_frame.png"
            cv2.imwrite(camera_frame_path, frame)
            return camera_frame_path
    return None

# Set up the GUI
root = ctk.CTk()
root.title("AI Chatbot Interface")

# Apply terminal theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

frame = ctk.CTkFrame(root, fg_color="black", border_color="green", border_width=2)
frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

output_box = Text(frame, height=10, wrap='word', bg="black", fg="green", insertbackground="green", bd=2, relief="solid", highlightbackground="green")
output_box.pack(fill=BOTH, expand=True, padx=10, pady=10)
output_box.tag_configure("user", foreground="#00FF00")
output_box.tag_configure("ai", foreground="#00FF00")

input_box = Text(frame, height=5, wrap='word', bg="black", fg="green", insertbackground="green", bd=2, relief="solid", highlightbackground="green")
input_box.pack(fill=BOTH, expand=True, padx=10, pady=10)
input_box.bind('<Return>', lambda event: send_query() if event.state & 1 else input_box.insert(END, '\n'))
input_box.bind('<Return>', send_query)


btn_frame = ctk.CTkFrame(root, fg_color="black", border_color="green", border_width=2)
btn_frame.pack(fill='x', padx=10, pady=10)

button_style = {"fg_color": 'black', "text_color": 'green', "hover_color": 'gray'}

btn1 = ctk.CTkButton(btn_frame, text="AI Input", command=toggle_audio_input, **button_style, width=10)
btn1.pack(side='left', padx=5, pady=5)

btn2 = ctk.CTkButton(btn_frame, text="Vision Input", command=toggle_vision_input, **button_style, width=10)
btn2.pack(side='left', padx=5, pady=5)

btn3 = ctk.CTkButton(btn_frame, text="Audio Output", command=toggle_audio_output, **button_style, width=10)
btn3.pack(side='left', padx=5, pady=5)

btn4 = ctk.CTkButton(btn_frame, text="Camera Input", command=toggle_camera_input, **button_style, width=10)
btn4.pack(side='left', padx=5, pady=5)

send_button = ctk.CTkButton(btn_frame, text="Send", command=send_query, **button_style, width=10)
send_button.pack(side='left', padx=5, pady=5)

quit_button = ctk.CTkButton(btn_frame, text="Quit", command=quit_app, **button_style, width=10)
quit_button.pack(side='left', padx=5, pady=5)

# Start the assistant loop in a separate thread
threading.Thread(target=assistant_loop).start()

root.mainloop()