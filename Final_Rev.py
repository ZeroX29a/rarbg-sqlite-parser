import sqlite3
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyperclip
import webbrowser

def connect_to_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        return conn, cursor
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to connect to database:\n{str(e)}")
        return None, None

def fuzzy_search(cursor, search_term, search_column, limit=None):
    search_term = re.sub(r'[.-]', '%', search_term)
    query = f"""
    SELECT rowid, title AS name, cat AS category, 
    CASE
        WHEN imdb IS NULL THEN '-'
        ELSE imdb
    END AS imdb, 
    DATE(dt) AS date,
    TIME(dt) AS time,
    CASE
        WHEN size < 1048576 THEN ROUND(size / 1024.0, 2) || ' KB'
        WHEN size < 1073741824 THEN ROUND(size / 1048576.0, 2) || ' MB'
        ELSE ROUND(size / 1073741824.0, 2) || ' GB'
    END AS Size
    FROM items
    WHERE {search_column} LIKE ?
    """
    if limit:
        query += f" LIMIT {limit}"
        
    cursor.execute(query, ('%' + search_term + '%',))
    results = cursor.fetchall()
    return results

def display_results(results):
    tree.delete(*tree.get_children())
    for idx, row in enumerate(results):
        tree.insert("", tk.END, values=(idx+1, row[1], row[2], row[3], row[4], row[5], row[6]))

def copy_to_clipboard(event):
    selected_item = tree.selection()
    if selected_item:
        item_index = tree.index(selected_item[0])
        rowid = results[item_index][0]
        query = "SELECT hash FROM items WHERE rowid = ?"
        cursor.execute(query, (rowid,))
        result = cursor.fetchone()
        if result:
            hash_val = result[0]
            magnet_link = f"magnet:?xt=urn:btih:{hash_val}"
            pyperclip.copy(magnet_link)
            messagebox.showinfo("Copied to Clipboard", "Magnet link copied to clipboard!")
        else:
            messagebox.showerror("Error", "Invalid selection.")
    else:
        messagebox.showerror("Error", "No item selected.")

def search(event=None):
    search_term = search_entry.get()
    search_column = search_column_var.get().lower()
    global results
    results = fuzzy_search(cursor, search_term, search_column)
    display_results(results)

def on_resize(event):
    if root.state() == 'zoomed':
        tree.column("Name", width=int(event.width * 0.4))
    else:
        tree.column("Name", width=350)

def open_imdb_link(event):
    region = tree.identify_region(event.x, event.y)
    column = tree.identify_column(event.x)
    if region == "cell" and column == "#4":  # Check if clicked on IMDB column
        selected_item = tree.selection()
        if selected_item:
            item_index = tree.index(selected_item[0])
            imdb_id = results[item_index][3]
            if imdb_id != '-':
                url = f"https://www.imdb.com/title/{imdb_id}"
                webbrowser.open(url)
            else:
                messagebox.showerror("Error", "No IMDB ID available.")

def sort_treeview(column):
    global sort_column, sort_reverse, default_sort
    if sort_column == column:
        if default_sort:
            sort_reverse = False
            default_sort = False
        else:
            sort_reverse = not sort_reverse
            if not sort_reverse:
                default_sort = True
    else:
        sort_reverse = False
        default_sort = False
    sort_column = column

    for item in tree.get_children():
        tree.delete(item)

    if default_sort:
        display_results(results)
    else:
        sorted_results = sorted(results, key=lambda x: x[columns.index(column)], reverse=sort_reverse)
        display_results(sorted_results)
    
    update_column_headings()

def update_column_headings():
    for col in columns:
        col_text = col
        if col == sort_column:
            if default_sort:
                col_text += " (-)"
            elif sort_reverse:
                col_text += " (↓)"
            else:
                col_text += " (↑)"
        else:
            col_text += " (-)"
        tree.heading(col, text=col_text, command=lambda _col=col: sort_treeview(_col))

def initialize_gui(conn, cursor, root):
    root.title("RARBG Parser")

    style = ttk.Style()
    style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"))
    style.configure("Treeview", font=("Helvetica", 10))

    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    search_label = tk.Label(frame, text="Enter search term:", font=("Helvetica", 12))
    search_label.pack(pady=5)

    global search_entry
    search_entry = tk.Entry(frame, width=50, font=("Helvetica", 12))
    search_entry.pack(pady=5)
    search_entry.bind('<Return>', lambda event: search())

    global search_column_var
    search_column_var = tk.StringVar()
    search_column_var.set("Name")  # Default column to search

    search_columns = ("Name", "Category", "IMDB", "Date", "Time")
    search_column_menu = ttk.OptionMenu(frame, search_column_var, "Name", *search_columns)
    search_column_menu.pack(pady=5)

    search_button = tk.Button(frame, text="Search", command=search, font=("Helvetica", 12))
    search_button.pack(pady=5)

    global columns
    columns = ("#", "Name", "Category", "IMDB", "Date", "Time", "Size")
    global tree
    tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)
    tree.heading("#", text="#")
    tree.heading("Name", text="Name", command=lambda: sort_treeview("Name"))
    tree.heading("Category", text="Category", command=lambda: sort_treeview("Category"))
    tree.heading("IMDB", text="IMDB")
    tree.heading("Date", text="Date", command=lambda: sort_treeview("Date"))
    tree.heading("Time", text="Time")
    tree.heading("Size", text="Size")
    tree.column("#", width=30)
    tree.column("Name", width=350)
    tree.column("Category", width=120)
    tree.column("IMDB", width=120, anchor="center")
    tree.column("Date", width=100)
    tree.column("Time", width=80)
    tree.column("Size", width=100)
    tree.pack(fill=tk.BOTH, expand=True, pady=5)

    # Display initial data limited to 50 items
    global results
    results = fuzzy_search(cursor, '', 'title', limit=50)  # Fetch initial data with limit
    display_results(results)

    root.bind("<Configure>", on_resize)

    tree.bind("<Double-1>", copy_to_clipboard)
    tree.bind("<Button-1>", open_imdb_link)

    copy_button = tk.Button(frame, text="Copy Magnet Link", command=copy_to_clipboard, font=("Helvetica", 12))
    copy_button.pack(pady=5)

    root.mainloop()

db_path = filedialog.askopenfilename(
    title="Select the rarbg database",
    filetypes=(("SQLite files", "*.sqlite"), ("All files", "*.*"))
)

if not db_path:
    exit()

conn, cursor = connect_to_db(db_path)

if not conn or not cursor:
    exit()

global sort_column, sort_reverse, default_sort
sort_column = "Name"
sort_reverse = False
default_sort = True

root = tk.Tk()
initialize_gui(conn, cursor, root)

if conn:
    conn.close()
