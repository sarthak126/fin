from pathlib import Path

import fitz


SRC = Path(r"C:\Users\sarth\Downloads\python sla.pdf")
OUT = Path(r"C:\Users\sarth\Downloads\file_manager_tool_using_java_report.pdf")
JAVA_FILE = Path(r"C:\Users\sarth\OneDrive\Desktop\ai\java_file_manager_demo\FileManagerTool.java")

CALIBRI = r"C:\Windows\Fonts\calibri.ttf"
CALIBRI_BOLD = r"C:\Windows\Fonts\calibrib.ttf"
TIMES = r"C:\Windows\Fonts\times.ttf"
TIMES_BOLD = r"C:\Windows\Fonts\timesbd.ttf"


def cover(page, rect):
    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)


def register_fonts(page):
    page.insert_font(fontname="calibri_file", fontfile=CALIBRI)
    page.insert_font(fontname="calibri_bold_file", fontfile=CALIBRI_BOLD)
    page.insert_font(fontname="times_file", fontfile=TIMES)
    page.insert_font(fontname="times_bold_file", fontfile=TIMES_BOLD)


def fit_box(page, rect, text, fontname, fontsize, min_size=10, align=0, color=(0, 0, 0)):
    size = fontsize
    while size >= min_size:
        spare = page.insert_textbox(rect, text, fontsize=size, fontname=fontname, align=align, color=color)
        if spare >= 0:
            return size, spare
        cover(page, rect)
        size -= 0.2
    raise RuntimeError(f"Text did not fit in box: {text[:60]!r}")


def write_lines(page, x, y, lines, fontname, fontsize=12, leading=12.9, color=(0, 0, 0)):
    cursor = y
    for line in lines:
        page.insert_text((x, cursor), line, fontname=fontname, fontsize=fontsize, color=color)
        cursor += leading


def main():
    doc = fitz.open(SRC)
    title = "FILE MANAGER TOOL USING JAVA"

    acknowledgement = (
        "We express our sincere gratitude to our project guide Y.K.Dhotre Sir, "
        "Department of Computer Technology, Sanjivani K. B. P. Polytechnic, "
        "Kopargaon, for his valuable guidance, encouragement, and continuous "
        "support throughout this microproject. His suggestions helped us plan "
        "the File Manager Tool in a structured and practical way.\n\n"
        "We are thankful to Head of Department Mr. S. A. Patil, Principal "
        "Mr. A. R. Mirikar, and all the faculty members of the Computer "
        "Technology Department for providing the facilities, motivation, and "
        "academic environment required to complete this project successfully. "
        "Their support encouraged us to improve the presentation and overall "
        "quality of the work.\n\n"
        "We also thank our parents, friends, and classmates for their constant "
        "encouragement and cooperation. This microproject on File Manager Tool "
        "using Java has been a valuable learning experience that improved our "
        "confidence in programming, logical thinking, and real-world problem "
        "solving."
    )

    introduction = (
        "A File Manager Tool using Java is a console-based application designed "
        "to perform basic file operations in a simple, organized, and efficient "
        "manner. In day-to-day computer usage, handling files manually can be "
        "time-consuming when users need to create, list, read, rename, or "
        "delete files repeatedly. This project provides a digital solution to "
        "manage such operations through a menu-driven program.\n\n"
        "The system allows users to create new files, display all files present "
        "in a workspace folder, read file content, rename existing files, and "
        "delete unnecessary files. By using Java, the project becomes reliable, "
        "structured, and suitable for understanding object-oriented as well as "
        "file-handling concepts.\n\n"
        "The main purpose of this microproject is to reduce manual effort, "
        "improve file organization, and provide a practical utility program for "
        "beginners. It also helps students understand important Java concepts "
        "such as classes, methods, conditions, loops, exception handling, and "
        "the java.nio.file package in a real application.\n\n"
        "This microproject demonstrates how Java programming can be used to "
        "develop a useful real-life tool while improving logical thinking, "
        "coding discipline, and problem-solving ability."
    )

    conclusion = (
        "The File Manager Tool developed using Java successfully demonstrates "
        "how programming can be applied to automate common file operations in a "
        "simple and practical manner. The project provides an organized way to "
        "create, list, read, rename, and delete files using a menu-driven "
        "system.\n\n"
        "By replacing repetitive manual actions with a Java application, file "
        "handling becomes faster, clearer, and more efficient. The program also "
        "shows how the java.nio.file package can be used effectively for modern "
        "file management tasks in real applications.\n\n"
        "During the development of this microproject, important Java concepts "
        "such as classes, methods, switch-case, exception handling, loops, and "
        "file operations were learned and applied practically. It also improved "
        "our confidence in logic building and structured program design.\n\n"
        "In conclusion, this project is a useful learning experience and a good "
        "foundation for developing more advanced desktop applications with "
        "graphical user interfaces, authentication, and advanced file "
        "management features in the future."
    )

    code_lines = JAVA_FILE.read_text(encoding="utf-8").splitlines()
    code_page_6 = code_lines[:44]
    code_page_7 = code_lines[44:]

    output_page_8 = [
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 1",
        "Enter file name: notes.txt",
        "Enter file content: Project documents are stored here.",
        "File created successfully!",
        "",
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 1",
        "Enter file name: report.txt",
        "Enter file content: Java microproject draft ready.",
        "File created successfully!",
        "",
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 2",
        "Files in workspace:",
        "- notes.txt",
        "- report.txt",
        "",
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 3",
        "Enter file name to read: notes.txt",
        "File content: Project documents are stored here.",
    ]

    output_page_9 = [
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 4",
        "Enter current file name: report.txt",
        "Enter new file name: final_report.txt",
        "File renamed successfully!",
        "",
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 2",
        "Files in workspace:",
        "- final_report.txt",
        "- notes.txt",
        "",
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 5",
        "Enter file name to delete: notes.txt",
        "File deleted successfully!",
        "",
        "===== File Manager Menu =====",
        "1. Create File",
        "2. List Files",
        "3. Read File",
        "4. Rename File",
        "5. Delete File",
        "6. Exit",
        "",
        "Enter your choice: 2",
        "Files in workspace:",
        "- final_report.txt",
        "",
        "Enter your choice: 6",
        "Exiting program...",
        "",
        "=== Code Execution Successful ===",
    ]

    references = [
        (
            "Oracle Java Documentation",
            [
                "The official Java documentation was used to understand syntax,",
                "class design, exception handling, and standard library usage.",
                "Website: https://docs.oracle.com/en/java/",
            ],
        ),
        (
            "Oracle NIO File API",
            [
                "This reference helped in using Files, Path, Paths, and",
                "StandardOpenOption for file creation and management.",
                "Website: https://docs.oracle.com/javase/tutorial/essential/io/",
            ],
        ),
        (
            "W3Schools - Java Tutorial",
            [
                "This source helped in revising Java basics such as methods,",
                "switch-case statements, loops, and user input handling.",
                "Website: https://www.w3schools.com/java/",
            ],
        ),
        (
            "GeeksforGeeks - Java File Handling",
            [
                "This platform was referred for file handling concepts,",
                "renaming logic, and practical examples of Java programs.",
                "Website: https://www.geeksforgeeks.org/java-file-class/",
            ],
        ),
        (
            "Class Notes and Study Material",
            [
                "Notes provided by teachers and classroom discussion helped in",
                "understanding the project requirements and implementation flow.",
            ],
        ),
    ]

    # Page 1: cover
    page = doc[0]
    register_fonts(page)
    cover(page, fitz.Rect(125, 196, 470, 240))
    fit_box(page, fitz.Rect(125, 200, 470, 235), title, "calibri_bold_file", 16, 13.5, 1)
    cover(page, fitz.Rect(230, 384, 366, 440))
    page.insert_textbox(
        fitz.Rect(225, 388, 370, 408),
        "Subject: JAVA",
        fontname="times_file",
        fontsize=15,
        align=1,
        color=(0, 0, 0),
    )
    cover(page, fitz.Rect(145, 416, 450, 446))
    page.insert_text(
        (202, 437),
        "JAVA PROGRAMMING",
        fontname="calibri_bold_file",
        fontsize=14,
        color=(0, 0, 0),
    )
    cover(page, fitz.Rect(150, 503, 450, 566))
    page.insert_textbox(
        fitz.Rect(150, 508, 450, 565),
        "Sarthak Nitin Bhokare (26)\nAditya Kailas Chavan (30)",
        fontname="times_bold_file",
        fontsize=14,
        align=1,
        color=(0, 0, 0),
    )
    cover(page, fitz.Rect(180, 670, 420, 712))
    page.insert_text(
        (238, 694),
        "Y.K.Dhotre Sir",
        fontname="calibri_bold_file",
        fontsize=15,
        color=(0, 0, 0),
    )

    # Page 2: certificate
    page = doc[1]
    register_fonts(page)
    cover(page, fitz.Rect(145, 368, 445, 404))
    fit_box(page, fitz.Rect(145, 372, 445, 398), title, "calibri_bold_file", 15.2, 13.0, 1)
    cover(page, fitz.Rect(105, 448, 435, 500))
    page.insert_textbox(
        fitz.Rect(105, 452, 435, 498),
        "Sarthak Nitin Bhokare (26)\nAditya Kailas Chavan (30)",
        fontname="times_file",
        fontsize=14,
        align=1,
        color=(0, 0, 0),
    )
    cover(page, fitz.Rect(68, 712, 265, 730))
    page.insert_textbox(
        fitz.Rect(68, 713, 265, 732),
        "Y.K.DHOTRE SIR",
        fontname="times_file",
        fontsize=13.2,
        align=1,
        color=(0, 0, 0),
    )

    # Page 3: acknowledgement
    page = doc[2]
    register_fonts(page)
    cover(page, fitz.Rect(60, 150, 530, 525))
    fit_box(page, fitz.Rect(60, 155, 530, 525), acknowledgement, "calibri_file", 13.9, 12.5, 3)
    cover(page, fitz.Rect(150, 570, 490, 625))
    page.insert_textbox(
        fitz.Rect(150, 574, 490, 624),
        "Sarthak Nitin Bhokare (26)\nAditya Kailas Chavan (30)",
        fontname="times_file",
        fontsize=14,
        align=2,
        color=(0, 0, 0),
    )

    # Page 4: index
    page = doc[3]
    register_fonts(page)
    cover(page, fitz.Rect(90, 220, 450, 560))
    page.insert_text((111, 245), "SR.NO", fontname="calibri_file", fontsize=12, color=(0, 0, 0))
    page.insert_text((255, 245), "TITLE", fontname="calibri_file", fontsize=12, color=(0, 0, 0))
    page.insert_text((396, 245), "PAGENO", fontname="calibri_file", fontsize=12, color=(0, 0, 0))
    rows = [
        ("1", "INTRODUCTION", "1"),
        ("2", "ACKNOWLEDGEMENT", "2"),
        ("3", "SOURCE CODE", "3"),
        ("4", "OUTPUT", "5"),
        ("5", "REFERENCE", "6"),
        ("6", "CONCLUSION", "7"),
    ]
    start_y = 308
    gap = 42
    for index, (sr_no, title_text, page_no) in enumerate(rows):
        y = start_y + index * gap
        page.insert_text((124, y), sr_no, fontname="calibri_file", fontsize=12, color=(0, 0, 0))
        page.insert_text((220, y), title_text, fontname="calibri_file", fontsize=12, color=(0, 0, 0))
        page.insert_text((414, y), page_no, fontname="calibri_file", fontsize=12, color=(0, 0, 0))

    # Page 5: introduction
    page = doc[4]
    register_fonts(page)
    cover(page, fitz.Rect(60, 225, 532, 690))
    fit_box(page, fitz.Rect(62, 228, 530, 690), introduction, "calibri_file", 14, 12.5, 3)

    # Page 6: source code
    page = doc[5]
    register_fonts(page)
    cover(page, fitz.Rect(60, 165, 532, 760))
    write_lines(page, 72, 187, code_page_6, "calibri_file", 11.0, 11.7)

    # Page 7: source code continuation
    page = doc[6]
    register_fonts(page)
    cover(page, fitz.Rect(60, 60, 532, 760))
    write_lines(page, 72, 84, code_page_7, "calibri_file", 11.0, 11.7)

    # Page 8: output
    page = doc[7]
    register_fonts(page)
    cover(page, fitz.Rect(60, 160, 532, 760))
    write_lines(page, 72, 174, output_page_8, "calibri_file", 11.5, 12.4)

    # Page 9: output continuation
    page = doc[8]
    register_fonts(page)
    cover(page, fitz.Rect(60, 60, 532, 760))
    write_lines(page, 72, 82, output_page_9, "calibri_file", 11.5, 12.4)

    # Page 10: reference
    page = doc[9]
    register_fonts(page)
    dark_blue = (0 / 255, 29 / 255, 53 / 255)
    link_blue = (0, 0, 1)
    cover(page, fitz.Rect(60, 170, 532, 700))
    y = 196
    for idx, (heading, lines) in enumerate(references):
        page.insert_text((72, y), "•", fontname="calibri_file", fontsize=14, color=dark_blue)
        page.insert_text((86, y), heading, fontname="calibri_bold_file", fontsize=14, color=dark_blue)
        y += 17
        for line in lines[:-1]:
            page.insert_text((72, y), line, fontname="calibri_file", fontsize=13.6, color=dark_blue)
            y += 17
        last_line = lines[-1]
        if last_line.startswith("Website: "):
            page.insert_text((72, y), "Website:", fontname="calibri_file", fontsize=13.6, color=dark_blue)
            page.insert_text((126, y), last_line.replace("Website: ", ""), fontname="calibri_file", fontsize=13.6, color=link_blue)
            y += 17
        else:
            page.insert_text((72, y), last_line, fontname="calibri_file", fontsize=13.6, color=dark_blue)
            y += 17
        if idx < len(references) - 1:
            y += 17

    # Page 11: conclusion
    page = doc[10]
    register_fonts(page)
    cover(page, fitz.Rect(60, 170, 532, 690))
    fit_box(page, fitz.Rect(62, 176, 530, 690), conclusion, "times_file", 14, 12.5, 3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    doc.close()
    print(OUT)


if __name__ == "__main__":
    main()
