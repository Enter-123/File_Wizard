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

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")

app.config['MYSQL_HOST'] = os.getenv("DB_HOST")
app.config['MYSQL_USER'] = os.getenv("DB_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("DB_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("DB_NAME")
app.config['MYSQL_PORT'] = int(os.getenv("DB_PORT", 3306))
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



LIBRE_OFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"



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




@app.route("/converter", methods=["GET", "POST"])
def converter():
    if "User_ID" not in session:
         flash("First Register/Login","error")
         return redirect(url_for('home'))
    
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("File Not Selected")
            return redirect(url_for("converter"))
        
        filename = secure_filename(file.filename)  
        

        if not filename.lower().endswith(".docx"):
            flash("Selected file is Not type Docx")
            return redirect(url_for("converter"))
        

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)  
        file.save(file_path)

        name, _ = os.path.splitext(filename)   
        output_pdf_name = f"{name}_{uuid.uuid4().hex[:6]}.pdf"
        output_pdf_path = os.path.join(app.config["OUTPUT_FOLDER"], output_pdf_name)

        try:
            subprocess.run(
            [
                LIBRE_OFFICE,
                "--headless", 
                "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", app.config["OUTPUT_FOLDER"],
                file_path
            ], 
            check=True
            )

            generated_pdf = os.path.join(app.config["OUTPUT_FOLDER"], f"{name}.pdf")
            if os.path.exists(generated_pdf):
                os.replace(generated_pdf, output_pdf_path)

                response = send_file(output_pdf_path, as_attachment=True, download_name=output_pdf_name)

                try:
                    os.remove(file_path)
                    os.remove(output_pdf_path)
                except Exception:
                    pass

                return response
            
            else:
                flash("Conversion Falied")
        except subprocess.CalledProcessError as e:
            flash(f"Conversion Error, {e}")
        except Exception as e:
            flash(f"Error, {str(e)}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    return render_template("converter.html")





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







TRIMMED_FOLDER = os.path.join(os.getcwd(), "trimmed")
os.makedirs(TRIMMED_FOLDER, exist_ok=True)

app.config["TRIMMED_FOLDER"] = TRIMMED_FOLDER


@app.route("/trimmer", methods=["GET", "POST"])
def trimmer():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))


    if request.method == "POST":
        video = request.files.get("video")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if not video or not start_time or not end_time:
            flash("Please upload a video and enter both start and end times.")
            return redirect(url_for("trimmer"))
        
        filename = secure_filename(video.filename)

        video_filename = f"{filename}_{uuid.uuid4().hex[:6]}"
        video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_filename)
        video.save(video_path)

        def time_to_seconds(t):
            parts = list(map(int, t.split(":")))
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            else:
                return int(parts[0])

        start_sec = time_to_seconds(start_time)
        end_sec = time_to_seconds(end_time)

        trimmed_filename = f"trimmed_{filename}"
        trimmed_path = os.path.join(app.config["TRIMMED_FOLDER"], trimmed_filename)

        try:
            clip = VideoFileClip(video_path).subclip(start_sec, end_sec)
            clip.write_videofile(trimmed_path, codec="libx264", audio_codec="aac")
            clip.close()
        except Exception as e:
            flash(f"Error trimming video: {e}")
            return redirect(url_for("trimmer"))
        
        try:
            os.remove(video_path)  # delete the uploaded file
        except Exception as e:
            print(f"Could not remove file {video_path}: {e}")

        return send_file(trimmed_path, as_attachment=True)

    return render_template("trimmer.html")



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



@app.route('/video_merge', methods=["GET", "POST"])
def video_merge():
    if "User_ID" not in session:
        flash("First Register/Login","error")
        return redirect(url_for('home'))    


    if request.method == "POST":
        video1 = request.files.get("video1")
        video2 = request.files.get("video2")

        if not video1 and not video2:
            flash("Both file should be selected")
            return redirect(url_for('video_merge'))
        
        video1_name = secure_filename(video1.filename)
        video2_name = secure_filename(video2.filename)
        video1_path = os.path.join(app.config["UPLOAD_FOLDER"], video1_name)
        video2_path = os.path.join(app.config["UPLOAD_FOLDER"], video2_name)
        video1.save(video1_path)
        video2.save(video2_path)


        if not video1_name.lower().endswith(".mp4") and not video2_name.lower().endswith(".mp4"):
            flash("Selected files is not a Video")
            os.remove(video1_path)
            os.remove(video2_path)
            return redirect(url_for('video_merge'))
        

        name1, _ = os.path.splitext(video1.filename)
        name2, _ = os.path.splitext(video2.filename)
        output_file_name = f"{name1}_{name2}_{uuid.uuid4().hex[:6]}.mp4"
        output_file_path = os.path.join(app.config["MERGED_FOLDER"], output_file_name)

        try:
            
            vid1 = VideoFileClip(video1_path)
            vid2 = VideoFileClip(video2_path)

            merge = concatenate_videoclips([vid1, vid2])
            merge.write_videofile(output_file_path)

            os.remove(video1_path)
            os.remove(video2_path)

            return send_file(
                output_file_path,
                as_attachment=True,
                download_name=output_file_name
            )

        except Exception as e:
            flash(f"Error Occurred: {str(e)}")
            return redirect(url_for('video_merge'))

    return render_template("video_merge.html")




if __name__ == "__main__":
    app.run(debug=True)