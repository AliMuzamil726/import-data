#include <iostream>
#include <string>
#include <iomanip> // For formatted output

using namespace std;

// Structure to hold student details
// Includes a pointer 'next' to link to the next student in the list
struct Student {
    int rollNumber;
    string name;
    float marks;
    Student* next;
};

// Global pointer to the head of the list
Student* head = nullptr;

// Function Prototypes
void addRecord();
void displayRecords();
void searchRecord();
void deleteRecord();
bool isRollNumberUnique(int rollNo);
void clearInputBuffer();

int main() {
    int choice;

    while (true) {
        // Menu Display
        cout << "\n========================================\n";
        cout << "   STUDENT RECORD MANAGEMENT SYSTEM\n";
        cout << "========================================\n";
        cout << "1. Add Student Record\n";
        cout << "2. Display All Records\n";
        cout << "3. Search Student Record\n";
        cout << "4. Delete Student Record\n";
        cout << "5. Exit\n";
        cout << "----------------------------------------\n";
        cout << "Enter your choice: ";
        
        // Input validation to ensure an integer is entered
        if (!(cin >> choice)) {
            cout << "Invalid input! Please enter a number.\n";
            clearInputBuffer();
            continue;
        }

        switch (choice) {
            case 1:
                addRecord();
                break;
            case 2:
                displayRecords();
                break;
            case 3:
                searchRecord();
                break;
            case 4:
                deleteRecord();
                break;
            case 5:
                cout << "Exiting program. Goodbye!\n";
                return 0;
            default:
                cout << "Invalid choice! Please select 1-5.\n";
        }
    }
}

// Helper function to clear the input stream (fixes skipping inputs)
void clearInputBuffer() {
    cin.clear();
    cin.ignore(1000, '\n');
}

// Check if a roll number already exists in the Linked List
bool isRollNumberUnique(int rollNo) {
    Student* temp = head;
    while (temp != nullptr) {
        if (temp->rollNumber == rollNo) {
            return false; // Found duplicate
        }
        temp = temp->next;
    }
    return true; // Unique
}

// 1. Add Student Record
void addRecord() {
    Student* newStudent = new Student();
    
    cout << "\n--- Add New Student ---\n";
    
    // Get Roll Number with Validation
    cout << "Enter Roll Number: ";
    while (!(cin >> newStudent->rollNumber)) {
        cout << "Invalid input! Enter a numeric Roll Number: ";
        clearInputBuffer();
    }

    // Check Uniqueness
    if (!isRollNumberUnique(newStudent->rollNumber)) {
        cout << "Error: Roll Number " << newStudent->rollNumber << " already exists!\n";
        delete newStudent; // Clean up memory since we aren't using it
        return;
    }

    clearInputBuffer(); // Clear buffer before reading string

    // Get Name
    cout << "Enter Name: ";
    getline(cin, newStudent->name);

    // Get Marks with Validation
    cout << "Enter Marks: ";
    while (!(cin >> newStudent->marks)) {
        cout << "Invalid input! Enter numeric Marks: ";
        clearInputBuffer();
    }

    // Insert at the end of the Linked List
    newStudent->next = nullptr;
    
    if (head == nullptr) {
        // If list is empty, new student becomes head
        head = newStudent;
    } else {
        // Traverse to the last node
        Student* temp = head;
        while (temp->next != nullptr) {
            temp = temp->next;
        }
        temp->next = newStudent;
    }

    cout << "Record added successfully!\n";
}

// 2. Display All Records
void displayRecords() {
    if (head == nullptr) {
        cout << "\nNo records found in the database.\n";
        return;
    }

    cout << "\n" << left << setw(10) << "Roll No" 
         << setw(20) << "Name" 
         << setw(10) << "Marks" << endl;
    cout << "----------------------------------------\n";

    Student* temp = head;
    while (temp != nullptr) {
        cout << left << setw(10) << temp->rollNumber 
             << setw(20) << temp->name 
             << setw(10) << temp->marks << endl;
        temp = temp->next;
    }
}

// 3. Search Student Record
void searchRecord() {
    if (head == nullptr) {
        cout << "\nDatabase is empty.\n";
        return;
    }

    int searchRoll;
    cout << "\nEnter Roll Number to search: ";
    cin >> searchRoll;

    Student* temp = head;
    bool found = false;

    while (temp != nullptr) {
        if (temp->rollNumber == searchRoll) {
            cout << "\n--- Record Found ---\n";
            cout << "Roll No: " << temp->rollNumber << endl;
            cout << "Name   : " << temp->name << endl;
            cout << "Marks  : " << temp->marks << endl;
            found = true;
            break;
        }
        temp = temp->next;
    }

    if (!found) {
        cout << "Student with Roll No " << searchRoll << " not found.\n";
    }
}

// 4. Delete Student Record
void deleteRecord() {
    if (head == nullptr) {
        cout << "\nDatabase is empty. Nothing to delete.\n";
        return;
    }

    int deleteRoll;
    cout << "\nEnter Roll Number to delete: ";
    cin >> deleteRoll;

    Student* temp = head;
    Student* prev = nullptr;

    // Case 1: The record to delete is the head (first node)
    if (temp != nullptr && temp->rollNumber == deleteRoll) {
        head = temp->next; // Move head to the next node
        delete temp;       // Free memory
        cout << "Record deleted successfully.\n";
        return;
    }

    // Case 2: Search for the record in the rest of the list
    while (temp != nullptr && temp->rollNumber != deleteRoll) {
        prev = temp;
        temp = temp->next;
    }

    // If temp is NULL, the record was not found
    if (temp == nullptr) {
        cout << "Student with Roll No " << deleteRoll << " not found.\n";
        return;
    }

    // Unlink the node from the list
    prev->next = temp->next;
    delete temp; // Free memory
    cout << "Record deleted successfully.\n";
}