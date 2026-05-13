from pathlib import Path

import fitz


SRC = Path(r"C:\Users\sarth\Downloads\python sla.pdf")
OUT = Path(r"C:\Users\sarth\Downloads\shopping_list_manager_python_report.pdf")
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

    ack_text = (
        "We express our sincere gratitude to Project Guide Mrs. S. R. Sisodiya, "
        "Department of Computer Technology, Sanjivani K. B. P. Polytechnic, "
        "Kopargaon, for her valuable guidance, encouragement, and continuous "
        "support during the development of this microproject. Her suggestions "
        "helped us understand the topic clearly and complete the work in a "
        "systematic manner.\n\n"
        "We are thankful to Head of Department Mr. S. A. Patil, Principal "
        "Mr. A. R. Mirikar, and all the faculty members of the Computer "
        "Technology Department for providing the facilities, motivation, and "
        "academic environment needed to complete this project successfully. "
        "Their support inspired us to improve the quality of our work.\n\n"
        "We also thank our parents, friends, and classmates for their constant "
        "encouragement and cooperation throughout the project. The microproject "
        "on Shopping List Manager using Python has been a useful learning "
        "experience that improved our confidence in programming, logical "
        "thinking, and practical problem solving."
    )

    intro_text = (
        "A Shopping List Manager is a Python-based application designed to help "
        "users organize day-to-day purchase items in a simple and efficient "
        "manner. In daily life, handwritten shopping notes are often misplaced, "
        "difficult to update, and inconvenient when the list keeps changing. "
        "This project provides a digital solution to store and manage details "
        "such as item id, item name, quantity, and category.\n\n"
        "The system allows users to add new items, display the full shopping "
        "list, search for a particular item, update quantity when requirements "
        "change, and remove unwanted items easily. By using Python, the project "
        "remains simple, flexible, and easy to understand for beginners.\n\n"
        "The main purpose of this microproject is to reduce manual effort, "
        "improve list accuracy, and provide a user-friendly way to manage "
        "shopping activities. It also helps students understand file handling, "
        "lists, functions, conditions, loops, and menu-driven program design in "
        "a practical way.\n\n"
        "This microproject demonstrates how Python Programming can be used to "
        "build a useful real-life application while improving logical thinking, "
        "data handling, and problem-solving skills."
    )

    conclusion_text = (
        "The Shopping List Manager developed using Python successfully "
        "demonstrates how basic programming can be used to solve an everyday "
        "problem in a practical and organized way. The project provides a "
        "simple method for storing shopping details such as item id, name, "
        "quantity, and category in a structured format.\n\n"
        "By replacing manual list writing with a computerized system, the "
        "process becomes faster, clearer, and easier to maintain. The program "
        "supports important operations like adding items, viewing the list, "
        "searching for records, updating quantities, and deleting unnecessary "
        "entries, which improves overall efficiency.\n\n"
        "During the development of this microproject, important Python concepts "
        "such as variables, lists, conditions, loops, functions, and file "
        "handling were learned and applied practically. It also helped in "
        "improving logical thinking and problem-solving ability.\n\n"
        "In conclusion, this project is a useful learning experience and a good "
        "foundation for developing more advanced applications with database "
        "support, user login, and graphical user interfaces in the future."
    )

    code_page_6 = [
        "import json",
        "",
        'FILE_NAME = "shopping_list.json"',
        "",
        "# Load data from file",
        "def load_data():",
        "    try:",
        '        with open(FILE_NAME, "r") as file:',
        "            return json.load(file)",
        "    except:",
        "        return []",
        "",
        "# Save data to file",
        "def save_data(items):",
        '    with open(FILE_NAME, "w") as file:',
        "        json.dump(items, file)",
        "",
        "shopping_list = load_data()",
        "",
        "def add_item():",
        '    item_id = int(input("Enter Item ID: "))',
        '    name = input("Enter Item Name: ")',
        '    quantity = int(input("Enter Quantity: "))',
        '    category = input("Enter Category: ")',
        '    item = {"id": item_id, "name": name,',
        '            "quantity": quantity, "category": category}',
        "    shopping_list.append(item)",
        "    save_data(shopping_list)",
        '    print("Item added successfully!\\n")',
        "",
        "def display_items():",
        "    if not shopping_list:",
        '        print("Shopping list is empty.\\n")',
        "    else:",
        '        print("\\nShopping List:")',
        "        for item in shopping_list:",
        '            print("ID:", item["id"], "| Name:", item["name"],',
        '                  "| Qty:", item["quantity"],',
        '                  "| Category:", item["category"])',
        "        print()",
        "",
        "def search_item():",
        '    item_id = int(input("Enter Item ID to search: "))',
        "    for item in shopping_list:",
        '        if item["id"] == item_id:',
        '            print("Item Found:", item)',
        "            return",
        '    print("Item not found.\\n")',
    ]

    code_page_7 = [
        "def update_item():",
        '    item_id = int(input("Enter Item ID to update: "))',
        "    for item in shopping_list:",
        '        if item["id"] == item_id:',
        '            item["quantity"] = int(input("Enter new quantity: "))',
        "            save_data(shopping_list)",
        '            print("Item updated successfully!\\n")',
        "            return",
        '    print("Item not found.\\n")',
        "",
        "def delete_item():",
        '    item_id = int(input("Enter Item ID to delete: "))',
        "    for item in shopping_list:",
        '        if item["id"] == item_id:',
        "            shopping_list.remove(item)",
        "            save_data(shopping_list)",
        '            print("Item deleted successfully!\\n")',
        "            return",
        '    print("Item not found.\\n")',
        "",
        "while True:",
        '    print("===== Shopping List Menu =====")',
        '    print("1. Add Item")',
        '    print("2. Display Items")',
        '    print("3. Search Item")',
        '    print("4. Update Quantity")',
        '    print("5. Delete Item")',
        '    print("6. Exit")',
        "",
        '    choice = int(input("Enter your choice: "))',
        "",
        "    if choice == 1:",
        "        add_item()",
        "    elif choice == 2:",
        "        display_items()",
        "    elif choice == 3:",
        "        search_item()",
        "    elif choice == 4:",
        "        update_item()",
        "    elif choice == 5:",
        "        delete_item()",
        "    elif choice == 6:",
        '        print("Exiting program...")',
        "        break",
        "    else:",
        '        print("Invalid choice!\\n")',
    ]

    output_page_8 = [
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 1",
        "Enter Item ID: 101",
        "Enter Item Name: Rice",
        "Enter Quantity: 2",
        "Enter Category: Grocery",
        "Item added successfully!",
        "",
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 1",
        "Enter Item ID: 102",
        "Enter Item Name: Soap",
        "Enter Quantity: 4",
        "Enter Category: Household",
        "Item added successfully!",
        "",
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 1",
        "Enter Item ID: 103",
        "Enter Item Name: Apples",
        "Enter Quantity: 6",
        "Enter Category: Fruits",
        "Item added successfully!",
    ]

    output_page_9 = [
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 2",
        "",
        "Shopping List:",
        "ID: 101 | Name: Rice | Qty: 2 | Category: Grocery",
        "ID: 102 | Name: Soap | Qty: 4 | Category: Household",
        "ID: 103 | Name: Apples | Qty: 6 | Category: Fruits",
        "",
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 3",
        "Enter Item ID to search: 102",
        "Item Found: {'id': 102, 'name': 'Soap', 'quantity': 4,",
        "            'category': 'Household'}",
        "",
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 4",
        "Enter Item ID to update: 101",
        "Enter new quantity: 3",
        "Item updated successfully!",
        "",
        "===== Shopping List Menu =====",
        "1. Add Item",
        "2. Display Items",
        "3. Search Item",
        "4. Update Quantity",
        "5. Delete Item",
        "6. Exit",
        "",
        "Enter your choice: 5",
        "Enter Item ID to delete: 103",
        "Item deleted successfully!",
        "",
        "Enter your choice: 6",
        "Exiting program...",
        "",
        "=== Code Execution Successful ===",
    ]

    ref_sections = [
        (
            "Python Official Documentation",
            [
                "The official documentation was used to understand Python syntax,",
                "functions, JSON handling, and file operations used in this project.",
                "Website: https://docs.python.org",
            ],
        ),
        (
            "W3Schools - Python Tutorial",
            [
                "This source helped in revising loops, conditions, functions, and",
                "basic menu-driven program structure in a simple manner.",
                "Website: https://www.w3schools.com/python",
            ],
        ),
        (
            "GeeksforGeeks - Python Programming",
            [
                "This platform was referred for list operations, searching logic,",
                "updating records, and beginner project examples.",
                "Website: https://www.geeksforgeeks.org/python-programming-language/",
            ],
        ),
        (
            "YouTube Tutorials",
            [
                "Educational videos were used to understand the practical steps",
                "involved in building small Python console applications.",
            ],
        ),
        (
            "Class Notes and Study Material",
            [
                "Notes provided by teachers and classroom discussion helped in",
                "understanding the project requirements and expected structure.",
            ],
        ),
    ]

    # Page 1
    page = doc[0]
    register_fonts(page)
    cover(page, fitz.Rect(120, 196, 475, 242))
    page.insert_textbox(
        fitz.Rect(118, 198, 477, 226),
        "SHOPPING LIST MANAGER USING PYTHON",
        fontname="calibri_bold_file",
        fontsize=16,
        align=1,
        color=(0, 0, 0),
    )
    cover(page, fitz.Rect(150, 500, 450, 575))
    page.insert_textbox(
        fitz.Rect(150, 508, 450, 565),
        "Sarthak Nitin Bhokare (26)\nAditya Kailas Chavan (30)",
        fontname="times_bold_file",
        fontsize=14,
        align=1,
        color=(0, 0, 0),
    )

    # Page 2
    page = doc[1]
    register_fonts(page)
    cover(page, fitz.Rect(145, 366, 445, 405))
    page.insert_textbox(
        fitz.Rect(145, 371, 445, 396),
        "SHOPPING LIST MANAGER USING PYTHON",
        fontname="calibri_bold_file",
        fontsize=15.5,
        align=1,
        color=(0, 0, 0),
    )
    cover(page, fitz.Rect(105, 448, 435, 500))
    page.insert_textbox(
        fitz.Rect(105, 452, 435, 498),
        "Sarthak Nitin Bhokare (26)\nAditya Kailas Chavan (30)",
        fontname="times_file",
        fontsize=14,
        align=1,
        color=(0, 0, 0),
    )

    # Page 3
    page = doc[2]
    register_fonts(page)
    cover(page, fitz.Rect(70, 150, 530, 535))
    fit_box(page, fitz.Rect(70, 155, 530, 535), ack_text, "calibri_file", 14, 12.5, 3)
    cover(page, fitz.Rect(160, 570, 490, 625))
    page.insert_textbox(
        fitz.Rect(155, 570, 490, 625),
        "Sarthak Nitin Bhokare (26)\nAditya Kailas Chavan (30)",
        fontname="times_file",
        fontsize=14,
        align=2,
        color=(0, 0, 0),
    )

    # Page 5
    page = doc[4]
    register_fonts(page)
    cover(page, fitz.Rect(60, 225, 532, 690))
    fit_box(page, fitz.Rect(62, 228, 530, 690), intro_text, "calibri_file", 14, 12.5, 3)

    # Page 6
    page = doc[5]
    register_fonts(page)
    cover(page, fitz.Rect(60, 165, 532, 760))
    write_lines(page, 72, 190, code_page_6, "calibri_file", 12, 12.9)

    # Page 7
    page = doc[6]
    register_fonts(page)
    cover(page, fitz.Rect(60, 60, 532, 760))
    write_lines(page, 72, 85, code_page_7, "calibri_file", 12, 12.9)

    # Page 8
    page = doc[7]
    register_fonts(page)
    cover(page, fitz.Rect(60, 160, 532, 760))
    write_lines(page, 72, 179, output_page_8, "calibri_file", 12, 12.9)

    # Page 9
    page = doc[8]
    register_fonts(page)
    cover(page, fitz.Rect(60, 60, 532, 760))
    write_lines(page, 72, 85, output_page_9, "calibri_file", 12, 12.9)

    # Page 10
    page = doc[9]
    register_fonts(page)
    dark_blue = (0 / 255, 29 / 255, 53 / 255)
    link_blue = (0, 0, 1)
    cover(page, fitz.Rect(60, 170, 532, 690))
    y = 195
    for idx, (title, body_lines) in enumerate(ref_sections):
        page.insert_text((72, y), "•", fontname="calibri_file", fontsize=14, color=dark_blue)
        page.insert_text((86, y), title, fontname="calibri_bold_file", fontsize=14, color=dark_blue)
        y += 17
        for line in body_lines[:-1]:
            page.insert_text((72, y), line, fontname="calibri_file", fontsize=14, color=dark_blue)
            y += 17
        last = body_lines[-1]
        if last.startswith("Website: "):
            page.insert_text((72, y), "Website:", fontname="calibri_file", fontsize=14, color=dark_blue)
            page.insert_text((126, y), last.replace("Website: ", ""), fontname="calibri_file", fontsize=14, color=link_blue)
            y += 17
        else:
            page.insert_text((72, y), last, fontname="calibri_file", fontsize=14, color=dark_blue)
            y += 17
        if idx < len(ref_sections) - 1:
            y += 17

    # Page 11
    page = doc[10]
    register_fonts(page)
    cover(page, fitz.Rect(60, 170, 532, 690))
    fit_box(page, fitz.Rect(62, 176, 530, 690), conclusion_text, "times_file", 14, 12.5, 3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    doc.close()
    print(OUT)


if __name__ == "__main__":
    main()
