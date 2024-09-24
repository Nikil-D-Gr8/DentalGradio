import gradio as gr
import assemblyai as aai
from transformers import pipeline
import os
from supabase import create_client, Client
from datetime import datetime
import csv
from typing import Optional

# Add your AssemblyAI API key as Environment Variable
aai.settings.api_key = os.environ['Assembly']
url: str = os.environ['DBUrl']
key: str = os.environ['DBKey']

# Initialize question answering pipeline
question_answerer = pipeline("question-answering", model='distilbert-base-cased-distilled-squad')

# List of questions
questions = [
    "How old is the patient?",
    "What is the gender?",
    "What is the chief complaint regarding the patient's oral health?",
    "List the Medical history mentioned",
    "Give the Dental history in detail",
    "Please give all the clinical findings which were listed"
]

# Oral Health Assessment Form
oral_health_assessment_form = [
    "Doctor's Name",
    "Location",
    "Patient's Name",
    "Age",
    "Gender",
    "Chief complaint",
    "Medical history",
    "Dental history",
    "Clinical Findings",
    "Treatment plan",
    "Referred to",
    "Calculus",
    "Stains"
]

# Function to generate answers for the questions
def generate_answer(question: str, context: str) -> str:
    result = question_answerer(question=question, context=context)
    return result['answer']

# Function to handle audio recording and transcription
def transcribe_audio(audio_path: str) -> str:
    print(f"Received audio file at: {audio_path}")
    
    if not os.path.exists(audio_path):
        return "Error: Audio file does not exist."
    
    if os.path.getsize(audio_path) == 0:
        return "Error: Audio file is empty."
    
    try:
        transcriber = aai.Transcriber()
        print("Starting transcription...")
        transcript = transcriber.transcribe(audio_path)
        print("Transcription process completed.")
        
        if transcript.status == aai.TranscriptStatus.error:
            print(f"Error during transcription: {transcript.error}")
            return transcript.error
        else:
            context = transcript.text
            print(f"Transcription text: {context}")
            return context
    
    except Exception as e:
        print(f"Exception occurred: {e}")
        return str(e)

# Function to fill in the answers for the text boxes
def fill_textboxes(context: str) -> list:
    answers = []
    for question in questions:
        answer = generate_answer(question, context)
        answers.append(answer)
    
    # Map answers to form fields in the correct order and return as a list
    return [
        answers[0] if len(answers) > 0 else "",  # Age
        answers[1] if len(answers) > 1 else "",  # Gender
        answers[2] if len(answers) > 2 else "",  # Chief complaint
        answers[3] if len(answers) > 3 else "",  # Medical history
        answers[4] if len(answers) > 4 else "",  # Dental history
        answers[5] if len(answers) > 5 else "",  # Clinical Findings
        "",  # Referred to
        "",  # Calculus
        "",  # Stains
    ]

# Supabase configuration
supabase: Client = create_client(url, key)

def handle_transcription(audio: str, doctor_name: str, location: str) -> list:
    context = transcribe_audio(audio)
    if "Error" in context:
        # Fill all fields with the error message
        return [context] * (len(textboxes_left) + len(textboxes_right) + 3)  # +3 for doctor_name, location, and treatment_plan
    
    answers = fill_textboxes(context)
    
    # Insert Doctor's Name and Location in the appropriate fields
    return [doctor_name, location] + answers + [""]  # Empty string for treatment_plan dropdown

def save_answers(doctor_name: str, location: str, patient_name: str, age: str, gender: str, chief_complaint: str, medical_history: str, dental_history: str, clinical_findings: str, treatment_plan: str, referred_to: str, calculus: str, stains: str) -> str:
    current_datetime = datetime.now().isoformat()
    answers_dict = {
        "Doctor's Name": doctor_name,
        "Location": location,
        "Patient's Name": patient_name,
        "Age": age,
        "Gender": gender,
        "Chief complaint": chief_complaint,
        "Medical history": medical_history,
        "Dental history": dental_history,
        "Clinical Findings": clinical_findings,
        "Treatment plan": treatment_plan,
        "Referred to": referred_to,
        "Calculus": calculus,
        "Stains": stains,
        "Submission Date and Time": current_datetime
    }
    print("Saved answers:", answers_dict)
    
    try:
        response = supabase.table('oral_health_assessments').insert(answers_dict).execute()
        print("Data inserted into Supabase:", response.data)
        return f"Saved answers: {answers_dict}"
    except Exception as e:
        print(f"Error inserting data into Supabase: {e}")
        return f"Error saving answers: {e}"

def download_table_to_csv() -> Optional[str]:
    response = supabase.table("oral_health_assessments").select("*").execute()
    
    if not response.data:
        print("No data found in the table.")
        return None

    data = response.data
    csv_data = []

    if len(data) > 0:
        csv_data.append(data[0].keys())  # Write header

    for row in data:
        csv_data.append(row.values())  # Write row values

    csv_file = "your_table.csv"
    with open(csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerows(csv_data)

    print("Downloaded table oral_health_assessments")
    return csv_file

def gradio_download() -> Optional[str]:
    file_path = download_table_to_csv()
    if file_path:
        return file_path
    return None

# Create the Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("# OHA Form Filler App")
    
    with gr.Tabs() as tabs:
        with gr.Tab("Doctor Info"):
            doctor_name_input = gr.Textbox(label="Doctor's Name", interactive=True)
            location_input = gr.Textbox(label="Location", interactive=True)
            submit_button = gr.Button("Submit")
            info_output = gr.HTML(label="Submitted Info")
            
            def submit_info(name, loc):
                return f"Doctor's Name: {name}<br>Location: {loc}"
            
            submit_button.click(fn=submit_info, inputs=[doctor_name_input, location_input], outputs=info_output)
        
        with gr.Tab("OHA Form"):
            audio_input = gr.Audio(type="filepath", label="Record your audio", elem_id="audio_input")
            transcribe_button = gr.Button("Transcribe and Generate Form", elem_id="transcribe_button", interactive=False)
            
            def enable_transcribe_button(audio):
                if audio:
                    return gr.update(interactive=True)
                return gr.update(interactive=False)
            
            audio_input.change(fn=enable_transcribe_button, inputs=audio_input, outputs=transcribe_button)

            with gr.Row(elem_id="textboxes_row"):
                with gr.Column():
                    doctor_name_display = gr.Textbox(label="Doctor's Name", value="", interactive=False)
                    location_display = gr.Textbox(label="Location", value="", interactive=False)
                    patient_name_input = gr.Textbox(label="Patient's Name", value="", interactive=True)
                    textboxes_left = [gr.Textbox(label=oral_health_assessment_form[i], value="", interactive=True) for i in range(3, 9)]  # Age, Gender, Chief complaint, Medical history, Dental history, Clinical Findings
                with gr.Column():
                    textboxes_right = [
                        gr.Dropdown(choices=["None", "Oral Medicine and Radiology", "Periodontics", "Oral Surgery", "Conservative and Endodontics", "Prosthodontics", "Pedodontics", "Orthodontics"], label="Referred to", interactive=True),
                        gr.Dropdown(choices=["+", "++", "+++"], label="Calculus", interactive=True),
                        gr.Dropdown(choices=[ "+", "++", "+++"], label="Stains", interactive=True),
                    ]
                    treatment_plan_dropdown = gr.Dropdown(choices=["Scaling", "Filling", "Pulp therapy/RCT", "Extraction", "Medication"], label="Treatment plan", interactive=True)

            oha_output = gr.Textbox(label="OHA Output", value="", interactive=False)
            save_button = gr.Button("Save to Supabase", elem_id="save_button", interactive=True)
            
            # Update the transcription and form fields when the transcribe button is clicked
            transcribe_button.click(
                fn=handle_transcription, 
                inputs=[audio_input, doctor_name_input, location_input], 
                outputs=[doctor_name_display, location_display] + textboxes_left + textboxes_right + [treatment_plan_dropdown]
            )
            
            # Save the form data to Supabase when the save button is clicked
            save_button.click(
                fn=save_answers, 
                inputs=[doctor_name_display, location_display, patient_name_input] + textboxes_left + [treatment_plan_dropdown] + textboxes_right, 
                outputs=[oha_output]
            )
        
        with gr.Tab("Download Data"):
            download_button = gr.Button("Download CSV")
            download_output = gr.File(label="Download the CSV File", interactive=False)
            
            download_button.click(fn=gradio_download, inputs=[], outputs=download_output)

# Launch the Gradio app
demo.launch(share=True)