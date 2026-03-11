#include <iostream>
#include <fstream>
#include <string>
#include <iomanip>

using namespace std;

// Using a standard name 'Node' often used in Data Structures classes
struct Node {
    int r_no;
    string name;
    float marks;
    Node* next;
};

Node* head = NULL; // Global head pointer
string fileName = "student_db.txt";

// Load data when program starts
void loadData() {
    ifstream fin(fileName);
    if (!fin) return; // if file doesn't exist, just return

    while (!fin.eof()) {
        Node* newNode = new Node;
        fin >> newNode->r_no;
        
        // check if we hit end of file
        if (fin.eof()) {
            delete newNode;
            break;
        }

        fin.ignore(); // clear buffer
        getline(fin, newNode->name);
        fin >> newNode->marks;
        newNode->next = NULL;

        // Add to end of list
        if (head == NULL) {
            head = newNode;
        } else {
            Node* temp = head;
            while (temp->next != NULL) {
                temp = temp->next;
            }
            temp->next = newNode;
        }
    }
    fin.close();
}

// Save data to file
void saveData() {
    ofstream fout(fileName);
    Node* temp = head;
    while (temp != NULL) {
        fout << temp->r_no << endl;
        fout << temp->name << endl;
        fout << temp->marks << endl;
        temp = temp->next;
    }
    fout.close();
}

void insertStudent() {
    Node* newNode = new Node;
    cout << "\n--- Add New Student ---\n";
    cout << "Enter Roll No: ";
    cin >> newNode->r_no;

    // Check for duplicate
    Node* check = head;
    while (check != NULL) {
        if (check->r_no == newNode->r_no) {
            cout << "Error: Roll Number already exists!\n";
            delete newNode;
            return;
        }
        check = check->next;
    }

    cin.ignore();
    cout << "Enter Name: ";
    getline(cin, newNode->name);
    cout << "Enter Marks: ";
    cin >> newNode->marks;

    newNode->next = NULL;

    // Logic to insert at end
    if (head == NULL) {
        head = newNode;
    } else {
        Node* temp = head;
        while (temp->next != NULL) {
            temp = temp->next;
        }
        temp->next = newNode;
    }
    cout << "Student added successfully.\n";
    saveData(); // Save immediately
}

void displayAll() {
    if (head == NULL) {
        cout << "\nList is empty.\n";
        return;
    }
    cout << "\nRoll No\tMarks\tName\n";
    cout << "----------------------------\n";
    Node* temp = head;
    while (temp != NULL) {
        cout << temp->r_no << "\t" << temp->marks << "\t" << temp->name << endl;
        temp = temp->next;
    }
}

void searchStudent() {
    int key;
    cout << "\nEnter Roll No to search: ";
    cin >> key;

    Node* temp = head;
    while (temp != NULL) {
        if (temp->r_no == key) {
            cout << "\nRecord Found:\n";
            cout << "Name: " << temp->name << endl;
            cout << "Marks: " << temp->marks << endl;
            return;
        }
        temp = temp->next;
    }
    cout << "Student not found.\n";
}

void deleteStudent() {
    int key;
    cout << "\nEnter Roll No to delete: ";
    cin >> key;

    if (head == NULL) {
        cout << "List is empty.\n";
        return;
    }

    // If head needs to be removed
    if (head->r_no == key) {
        Node* toDelete = head;
        head = head->next;
        delete toDelete;
        cout << "Record deleted.\n";
        saveData();
        return;
    }

    Node* curr = head;
    Node* prev = NULL;

    while (curr != NULL && curr->r_no != key) {
        prev = curr;
        curr = curr->next;
    }

    if (curr == NULL) {
        cout << "Record not found.\n";
        return;
    }

    prev->next = curr->next;
    delete curr;
    cout << "Record deleted.\n";
    saveData();
}

int main() {
    loadData(); // Load previous data
    int choice;

    do {
        cout << "\n=== Student Management System ===\n";
        cout << "1. Add Student Record\n";
        cout << "2. Display All Records\n";
        cout << "3. Search by Roll No\n";
        cout << "4. Delete Record\n";
        cout << "5. Exit\n";
        cout << "Enter your choice: ";
        cin >> choice;

        if(cin.fail()){
            cin.clear(); cin.ignore(1000,'\n');
            choice = 0;
        }

        switch (choice) {
            case 1: insertStudent(); break;
            case 2: displayAll(); break;
            case 3: searchStudent(); break;
            case 4: deleteStudent(); break;
            case 5: 
                saveData();
                cout << "Exiting...\n"; 
                break;
            default: cout << "Invalid choice. Try again.\n";
        }
    } while (choice != 5);

    return 0;
}