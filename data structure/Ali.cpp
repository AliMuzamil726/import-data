#include <iostream>
#include <string>
#include <fstream>

using namespace std;

// Struct definition
struct Candidate {
    int id;
    string name;
    float gpa;
    Candidate *link; // linking pointer
};

Candidate *root = NULL; // Initialize to NULL

// Prototypes
void createEntry();
void listEntries();
void queryEntry();
void dropEntry();
void dumpToFile();
void readFromFile();

int main() {
    readFromFile(); // Auto-load

    int userSel;
    
    // Using an infinite for-loop instead of while
    for(;;) {
        cout << "\n--- CLASS RECORD SYSTEM ---\n";
        cout << "[1] Add Candidate\n";
        cout << "[2] List Candidates\n";
        cout << "[3] Search\n";
        cout << "[4] Delete\n";
        cout << "[5] Save & Exit\n";
        cout << "Select >> ";
        
        cin >> userSel;

        if(cin.fail()) {
            cin.clear();
            cin.ignore(500, '\n');
            cout << "Input Error.\n";
            continue;
        }

        // Using if-else logic instead of switch
        if (userSel == 1) {
            createEntry();
        } 
        else if (userSel == 2) {
            listEntries();
        } 
        else if (userSel == 3) {
            queryEntry();
        } 
        else if (userSel == 4) {
            dropEntry();
        } 
        else if (userSel == 5) {
            dumpToFile();
            cout << "Data saved. Terminating.\n";
            break; // Break the infinite loop
        } 
        else {
            cout << "Unknown command.\n";
        }
    }
    return 0;
}

// File Reading
void readFromFile() {
    ifstream in("candidates.dat");
    if (!in) return; // No file, do nothing

    while (!in.eof()) {
        Candidate *temp = new Candidate;
        in >> temp->id;
        
        if (in.eof()) {
            delete temp;
            break;
        }
        
        in.ignore();
        getline(in, temp->name);
        in >> temp->gpa;
        temp->link = NULL;

        // Add to list end
        if (root == NULL) {
            root = temp;
        } else {
            Candidate *p = root;
            while (p->link != NULL) {
                p = p->link;
            }
            p->link = temp;
        }
    }
    in.close();
}

// File Writing
void dumpToFile() {
    ofstream out("candidates.dat");
    Candidate *p = root;
    while (p != NULL) {
        out << p->id << endl;
        out << p->name << endl;
        out << p->gpa << endl;
        p = p->link;
    }
    out.close();
}

void createEntry() {
    Candidate *node = new Candidate;
    cout << "ID Number: ";
    cin >> node->id;

    // Check uniqueness manually here
    Candidate *check = root;
    bool exists = false;
    while(check != NULL) {
        if(check->id == node->id) {
            exists = true; 
            break; 
        }
        check = check->link;
    }

    if(exists) {
        cout << "Error: ID exists.\n";
        delete node;
        return;
    }

    cin.ignore();
    cout << "Name: ";
    getline(cin, node->name);
    cout << "GPA/Marks: ";
    cin >> node->gpa;
    
    node->link = NULL;

    if (root == NULL) {
        root = node;
    } else {
        Candidate *walker = root;
        while (walker->link != NULL) {
            walker = walker->link;
        }
        walker->link = node;
    }
    dumpToFile(); // Save immediately
    cout << "Success.\n";
}

void listEntries() {
    if (root == NULL) {
        cout << "Empty Database.\n";
        return;
    }
    cout << "\nID\tGPA\tName\n";
    cout << "----------------------\n";
    Candidate *ptr = root;
    while (ptr != NULL) {
        cout << ptr->id << "\t" << ptr->gpa << "\t" << ptr->name << endl;
        ptr = ptr->link;
    }
}

void queryEntry() {
    int target;
    cout << "Enter ID to find: ";
    cin >> target;
    
    Candidate *ptr = root;
    while (ptr != NULL) {
        if (ptr->id == target) {
            cout << "Record: " << ptr->name << " -- " << ptr->gpa << endl;
            return;
        }
        ptr = ptr->link;
    }
    cout << "Not found.\n";
}

void dropEntry() {
    int target;
    cout << "Enter ID to delete: ";
    cin >> target;

    if (root == NULL) return;

    if (root->id == target) {
        Candidate *toDelete = root;
        root = root->link;
        delete toDelete;
        dumpToFile();
        cout << "Deleted.\n";
        return;
    }

    Candidate *current = root;
    Candidate *previous = NULL;

    while (current != NULL && current->id != target) {
        previous = current;
        current = current->link;
    }

    if (current == NULL) {
        cout << "ID not found.\n";
    } else {
        previous->link = current->link;
        delete current;
        dumpToFile();
        cout << "Deleted.\n";
    }
}