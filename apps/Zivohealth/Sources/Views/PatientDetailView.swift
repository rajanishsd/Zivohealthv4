import SwiftUI

struct PatientDetailView: View {
    let patient: Patient
    @StateObject private var viewModel = PatientViewModel()
    @State private var selectedMetricType = "Blood Pressure"
    @State private var showingAddMetric = false

    private let metricTypes = ["Blood Pressure", "Heart Rate", "Blood Sugar", "Temperature", "Weight"]

    var body: some View {
        List {
            Section {
                DetailRow(title: "Name", value: patient.name)
                DetailRow(title: "Date of Birth", value: patient.dateOfBirth.formatted(date: .long, time: .omitted))
                DetailRow(title: "Gender", value: patient.gender)
            } header: {
                Text("Personal Information")
            }

            Section {
                DetailRow(title: "Phone", value: patient.contactNumber)
                DetailRow(title: "Email", value: patient.email)
                DetailRow(title: "Address", value: patient.address)
            } header: {
                Text("Contact Information")
            }

            Section {
                Picker("Metric Type", selection: $selectedMetricType) {
                    ForEach(metricTypes, id: \.self) { type in
                        Text(type).tag(type)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.vertical, 8)

                let filteredMetrics = patient.healthMetrics.filter { $0.type == selectedMetricType }
                ForEach(filteredMetrics) { metric in
                    MetricRow(metric: metric)
                }
            } header: {
                Text("Health Metrics")
            }

            if !patient.labReports.isEmpty {
                Section {
                    ForEach(patient.labReports) { report in
                        NavigationLink {
                            LabReportDetailView(report: report)
                        } label: {
                            VStack(alignment: .leading) {
                                Text(report.testName)
                                    .font(.headline)
                                Text(report.date.formatted(date: .abbreviated, time: .omitted))
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                } header: {
                    Text("Lab Reports")
                }
            }
        }
        .navigationTitle("Patient Details")
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button(action: { showingAddMetric = true }) {
                    Image(systemName: "plus")
                }
            }
        }

    }
}

struct DetailRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack {
            Text(title)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
        }
    }
}

struct MetricRow: View {
    let metric: HealthMetric

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("\(metric.value, specifier: "%.1f") \(metric.unit)")
                    .font(.headline)
                Spacer()
                Text(metric.date.formatted(date: .abbreviated, time: .shortened))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if let notes = metric.notes, !notes.isEmpty {
                Text(notes)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

struct LabReportDetailView: View {
    let report: LabReport

    var body: some View {
        List {
            Section {
                DetailRow(title: "Test Name", value: report.testName)
                DetailRow(title: "Date", value: report.date.formatted(date: .long, time: .omitted))
                DetailRow(title: "Results", value: report.testResults)
                DetailRow(title: "Normal Range", value: report.normalRange)
                DetailRow(title: "Unit", value: report.unit)
            } header: {
                Text("Test Information")
            }

            Section {
                DetailRow(title: "Lab Name", value: report.labName)
                DetailRow(title: "Doctor", value: report.doctorName)
            } header: {
                Text("Provider Information")
            }
        }
        .navigationTitle("Lab Report")
    }
}

#Preview {
    NavigationView {
        PatientDetailView(
            patient: Patient(
                name: "John Doe",
                dateOfBirth: Date(),
                gender: "Male",
                contactNumber: "+1 234 567 8900",
                email: "john@example.com",
                address: "123 Health St, Medical City, MC 12345"
            )
        )
    }
}
