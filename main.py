from flask import Flask, render_template, redirect, url_for, request, session, flash, send_file
from flask_mysqldb import MySQL
import subprocess
import uuid
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip, concatenate_videoclips
from pdf2docx import Converter
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
import pikepdf
import os, zipfile, io
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")

app.config['MYSQL_HOST'] = os.getenv("DB_HOST")
app.config['MYSQL_USER'] = os.getenv("DB_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("DB_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("DB_NAME")
app.config['MYSQL_PORT'] = int(os.getenv("DB_PORT"))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'


mysql = MySQL(app)


UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads") 
OUTPUT_FOLDER = os.path.join(os.getcwd(), "converts")
PROCESSED_FOLDER = os.path.join(os.getcwd(), "process")
MERGED_FOLDER = os.path.join(os.getcwd(), "merged")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(MERGED_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["MERGED_FOLDER"] = MERGED_FOLDER




@app.route("/")
@app.route("/home")
def home():
    # if "User_ID" not in session:
    #     flash("First Login","error")
    #     return redirect(url_for('login'))
    
    name = session.get("First_Name")
    return render_template("home.html", name=name)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM AppDB WHERE Email_ID = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user is None:
            flash("Email Doesn't Exist", "error")
            return redirect(url_for('login'))

        if user['Pass_Word'] != password:
            flash("Invalid Password", "error")
            return redirect(url_for('login'))

        session.clear()
        session["User_ID"] = user["User_ID"]
        session["First_Name"] = user["First_Name"]
        return redirect(url_for('home'))

    return render_template("login.html")




@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fname = request.form.get("firstname")
        lname = request.form.get("lastname")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm = request.form.get("con-password")

        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for('signup'))

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO AppDB (First_Name, Last_Name, Email_ID, Pass_Word) VALUES (%s, %s, %s, %s)",
                (fname, lname, email, password)
            )
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('signup'))

    return render_template("signup.html")





@app.route("/image_resizer", methods=["GET", "POST"])
def image_resizer():
    if "User_ID" not in session:
        flash("First Register/Login", "error")
        return redirect(url_for('home'))

    if request.method == "POST":
        file = request.files.get("file")
        width = request.form.get("width")
        height = request.form.get("height")

        if not file:
            flash("No file selected")
            return redirect(url_for("image_resizer"))

        if not width or not height or not width.isdigit() or not height.isdigit():
            flash("Please provide valid width and height values.")
            return redirect(url_for("image_resizer"))

        width = int(width)
        height = int(height)

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        try:

            with Image.open(file_path) as img:

                resized_img = img.resize((width, height))


                output_name = f"resized_{uuid.uuid4().hex[:6]}.png"
                output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_name)
                resized_img.save(output_path)

                resized_img.save(output_path)

                return send_file(output_path, as_attachment=True, download_name=output_name)

        except Exception as e:
            flash(f"Error: {str(e)}")
        finally:

            if os.path.exists(file_path):
                os.remove(file_path)

    return render_template("image_resizer.html")





@app.route("/pdf_to_word", methods=["GET", "POST"])
def pdf_to_word():
    if "User_ID" not in session:
        flash("First Register/Login", "error")
        return redirect(url_for('home'))
    
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("File Not Selected", "error")
            return redirect(url_for("pdf_to_word"))
        
        filename = secure_filename(file.filename)

        # Accept only PDF files
        if not filename.lower().endswith(".pdf"):
            flash("Selected file is not a PDF", "error")
            return redirect(url_for("pdf_to_word"))
        
        # Save uploaded PDF with unique name
        unique_filename = f"{uuid.uuid4().hex[:6]}_{filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(file_path)

        # Create DOCX output file path
        name, _ = os.path.splitext(unique_filename)
        output_docx_name = f"{name}.docx"
        output_docx_path = os.path.join(app.config["OUTPUT_FOLDER"], output_docx_name)

        try:
            # Convert PDF to Word
            cv = Converter(file_path)
            cv.convert(output_docx_path, start=0, end=None)  # full document
            cv.close()

            if os.path.exists(output_docx_path):
                response = send_file(output_docx_path, as_attachment=True, download_name=output_docx_name)

                # Clean up files after sending
                try:
                    os.remove(file_path)
                    os.remove(output_docx_path)
                except Exception as e:
                    print(f"Cleanup failed: {e}")

                return response
            else:
                flash("Conversion failed: DOCX not generated", "error")

        except Exception as e:
            flash(f"Error during conversion: {str(e)}", "error")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return render_template("pdf_to_word.html")












@app.route("/video_to_gif", methods=["GET", "POST"])
def video_to_gif():
    if "User_ID" not in session:
        flash("First Register/Login", "error")
        return redirect(url_for('home'))

    if request.method == "POST":
        video = request.files.get("video")
        if not video:
            flash("No video selected")
            return redirect(url_for("video_to_gif"))

        start_time = float(request.form["start_time"])
        end_time = float(request.form["end_time"])

        if end_time - start_time > 5:
            flash("The GIF duration cannot exceed 5 seconds.")
            return redirect(url_for("video_to_gif"))

        filename = secure_filename(video.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        video.save(file_path)

        output_name = f"{os.path.splitext(filename)[0]}_{uuid.uuid4().hex[:6]}.gif"
        output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_name)

        try:
            clip = VideoFileClip(file_path).subclip(start_time, end_time)
            clip.write_gif(output_path)  # No ffmpeg codecs needed
            clip.close()

            return send_file(output_path, as_attachment=True, download_name=output_name)

        except Exception as e:
            flash(f"Error: {str(e)}")

    return render_template("video_to_gif.html")








@app.route('/mp4_to_mp3', methods=["GET", "POST"])
def mp4_to_mp3():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))


    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("No file Selected")
            return redirect(url_for('mp4_to_mp3'))

        filename = secure_filename(file.filename)

        if not filename.lower().endswith(".mp4"):
            flash("Selected file is not Type MP4")
            return redirect(url_for('mp4_to_mp3'))
        
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)


        name, _ = os.path.splitext(filename)
        output_file_name = f"{name}_{uuid.uuid4().hex[:6]}.mp3"
        output_file_path = os.path.join(app.config["OUTPUT_FOLDER"], output_file_name)

        try:
            videoclip = VideoFileClip(file_path)

            audioclip = videoclip.audio
            audioclip.write_audiofile(output_file_path)

            if os.path.exists(output_file_path):
                response = send_file(output_file_path, as_attachment=True, download_name=output_file_name)

                try:
                    os.remove(file_path)
                    os.remove(output_file_path)
                except Exception as e:
                    print(f"Cleanup failed: {e}")

                return response
            else:
                flash("Conversion failed: MP3 not generated", "error")

        except Exception as e:
            flash(f"Error during conversion {str(e)}","error")
        finally: 
            videoclip.close()
            audioclip.close()
            if os.path.exists(file_path):
                os.remove(file_path)


    return render_template('mp4_to_mp3.html')






@app.route('/delete_pdf_pages', methods=["GET", "POST"])
def delete_pdf_pages():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))
    
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("File Not selected")
            return redirect(url_for('delete_pdf_pages'))

        filename = secure_filename(file.filename)

        if not filename.lower().endswith(".pdf"):
            flash("Selected File is not Type PDF")
            return redirect(url_for('delete_pdf_pages'))
        
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        return render_template("delete_pdf_pages.html", filename=filename, total_pages=total_pages)

    return render_template("delete_pdf_pages.html")



@app.route('/delete_pages', methods=["POST"])
def delete_pages():
    filename = request.form["filename"]
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    reader = PdfReader(file_path)
    writer = PdfWriter()

    pages_to_delete = [int(i) for i in request.form.getlist("pages")]

    name,_ = os.path.splitext(filename)
    output_file_name = f"{name}_{uuid.uuid4().hex[:6]}.pdf"
    output_file_path = os.path.join(app.config["PROCESSED_FOLDER"], output_file_name)

    for i in range(len(reader.pages)):
        if i not in pages_to_delete:
            writer.add_page(reader.pages[i])

    try:
        with open(output_file_path, "wb") as f:
            writer.write(f)

        if os.path.exists(file_path):
            os.remove(file_path)

        flash("File Processed Sucssfully Click Below to Download")
        session["download_file"] = output_file_name
    except Exception as e:
        flash(f"Error Occured as {str(e)}")

    return redirect(url_for('delete_pdf_pages'))


@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
    session.pop("download_file", None)
    return send_file(path, as_attachment=True)




@app.route('/pdf_merge', methods=["GET", "POST"])
def pdf_merge():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))

    if request.method == "POST":
        files = request.files.getlist("file")
        file_list = []

        if not files:
            flash(f"No file Selected")
            return redirect(url_for('pdf_merge'))

        for file in files:
            f2 = secure_filename(file.filename)
            if f2.lower().endswith(".pdf"):
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], f2)
                file.save(file_path)
                file_list.append(file_path)
            else:
                flash(f"Selected file is not a PDF file", "error")
                return redirect(url_for('pdf_merge'))  

        if not file_list:
            flash("No valid PDF uploaded", "error")
            return redirect(url_for('pdf_merge'))

        output_file_name = f"{'merge'}_{uuid.uuid4().hex[:6]}.pdf"
        output_file_path = os.path.join(app.config["MERGED_FOLDER"], output_file_name)

        try:
            merger = PdfMerger()

            for f in file_list:
                merger.append(f)
            merger.write(output_file_path)
            merger.close()

            for f in file_list:
                os.remove(f)

            return send_file(output_file_path, as_attachment=True)
        
        except Exception as e:
            flash(f"Error Occured {str(e)}")

    return render_template("pdf_merge.html")




@app.route('/excel_to_csv', methods=["GET","POST"])
def excel_to_csv():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))


    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("File Not Selected")
            return redirect(url_for('excel_to_csv'))
        
        filename = secure_filename(file.filename)

        if not filename.lower().endswith((".xlsx", ".xls")):
            flash("Only Upload Excel File")
            return redirect(url_for('excel_to_csv'))
        
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        name, _ = os.path.splitext(filename)
        output_csv_name = f"{name}_{uuid.uuid4().hex[:6]}.csv"
        output_csv_path = os.path.join(app.config["OUTPUT_FOLDER"], output_csv_name)


        try:
            import pandas as pd

            df = pd.read_excel(file_path)

            df.to_csv(output_csv_path, index=False)

            response = send_file(output_csv_path, as_attachment=True, download_name=output_csv_name)

            try:
                os.remove(file_path)
                os.remove(output_csv_path)
            except Exception:
                pass

            return response
        
        except Exception as e:
            flash(f"Error Occured as {str(e)}")

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
        
    return render_template('excel_to_csv.html')





@app.route('/pdf_split', methods=["GET", "POST"])
def pdf_split():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))


    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("No file selected")
            return redirect(url_for('pdf_split'))
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        if not filename.lower().endswith(".pdf"):
            flash("Selected file is not a PDF")
            os.remove(file_path)
            return redirect(url_for('pdf_split'))

        try:
            memory_file = io.BytesIO()

            with zipfile.ZipFile(memory_file, 'w') as zipf:
                with pikepdf.Pdf.open(file_path) as old_pdf:
                    for n, page_can in enumerate(old_pdf.pages):
                        new_pdf = pikepdf.Pdf.new()
                        new_pdf.pages.append(page_can)

                        page_name = f"page_{n+1}.pdf"

                        page_buffer = io.BytesIO()
                        new_pdf.save(page_buffer)
                        page_buffer.seek(0)

                        zipf.writestr(page_name, page_buffer.read())

            memory_file.seek(0)

            os.remove(file_path)
            
            return send_file(
                memory_file,
                as_attachment=True,
                download_name="split_pdfs.zip",
                mimetype="application/zip"
            )

        except Exception as e:
            flash(f"Error Occurred: {str(e)}")
            return redirect(url_for('pdf_split'))

    return render_template("split_pdf_pages.html")




@app.route("/video_thumbnail", methods=["GET", "POST"])
def video_thumbnail():
    if "User_ID" not in session:
        flash("First Register/Login", "error")
        return redirect(url_for('home'))

    if request.method == "POST":
        # Get video file
        video = request.files.get("video")
        if not video:
            flash("No video selected")
            return redirect(url_for("video_thumbnail"))

        # Get the timestamp for the thumbnail (in seconds)
        timestamp = request.form.get("time")
        try:
            timestamp = float(timestamp)  # Convert to float for seconds
        except ValueError:
            flash("Invalid timestamp. Please enter a valid number in seconds.")
            return redirect(url_for("video_thumbnail"))

        # Save the uploaded video
        filename = secure_filename(video.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        video.save(file_path)

        # Generate output filename for the thumbnail
        output_name = f"{os.path.splitext(filename)[0]}_{uuid.uuid4().hex[:6]}.jpg"
        output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_name)

        try:
            # Load the video and extract the frame at the specified timestamp
            clip = VideoFileClip(file_path)

            # Check if timestamp is within the video's duration
            if timestamp < 0 or timestamp > clip.duration:
                flash(f"Timestamp must be between 0 and {clip.duration} seconds.")
                return redirect(url_for("video_thumbnail"))

            # Extract the frame at the specified timestamp
            frame = clip.get_frame(timestamp)
            img = Image.fromarray(frame)
            img.save(output_path)

            clip.close()

            # Send the image file as a download
            return send_file(output_path, as_attachment=True, download_name=output_name)

        except Exception as e:
            flash(f"Error: {str(e)}")
            return redirect(url_for("video_thumbnail"))

    return render_template("video_thumbnail.html")




if __name__ == "__main__":
    app.run(debug=True)
