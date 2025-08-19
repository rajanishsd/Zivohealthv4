import Foundation
import SwiftUI

struct PatientListView: View {
    @StateObject private var viewModel = PatientViewModel()
    @State private var showingAddPatient = false

    var body: some View {
        List {
            ForEach(viewModel.patients) { patient in
                NavigationLink {
                    PatientDetailView(patient: patient)
                } label: {
                    PatientRowView(patient: patient)
                }
            }
        }
        .navigationTitle("Patients")
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                Button(action: { showingAddPatient = true }) {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showingAddPatient) {
            AddPatientView(viewModel: viewModel)
        }
        .onAppear {
            viewModel.loadPatients()
        }
    }
}

struct PatientRowView: View {
    let patient: Patient

    var body: some View {
        VStack(alignment: .leading) {
            Text(patient.name)
                .font(.headline)
            Text(patient.email)
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
    }
}

struct AddPatientView: View {
    @Environment(\.dismiss) private var dismiss
    let viewModel: PatientViewModel

    @State private var name = ""
    @State private var dateOfBirth = Date()
    @State private var gender = "Male"
    @State private var contactNumber = ""
    @State private var email = ""
    @State private var address = ""

    let genders = ["Male", "Female", "Other"]

    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Personal Information")) {
                    TextField("Name", text: $name)
                    DatePicker("Date of Birth", selection: $dateOfBirth, displayedComponents: .date)
                    Picker("Gender", selection: $gender) {
                        ForEach(genders, id: \.self) { gender in
                            Text(gender)
                        }
                    }
                }

                Section(header: Text("Contact Information")) {
                    TextField("Contact Number", text: $contactNumber)
                    TextField("Email", text: $email)
                    TextField("Address", text: $address)
                }
            }
            .navigationTitle("Add Patient")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        viewModel.addPatient(
                            name: name,
                            dateOfBirth: dateOfBirth,
                            gender: gender,
                            contactNumber: contactNumber,
                            email: email,
                            address: address
                        )
                        dismiss()
                    }
                    .disabled(name.isEmpty || email.isEmpty)
                }
            }
        }
    }
}

#Preview {
    PatientListView()
}
