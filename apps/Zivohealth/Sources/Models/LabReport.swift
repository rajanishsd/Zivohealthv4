import Foundation

struct LabReport: Identifiable, Codable, Hashable, Equatable {
    let id: String = UUID().uuidString
    var date: Date = .init()
    var testName: String = ""
    var testResults: String = ""
    var normalRange: String = ""
    var unit: String = ""
    var labName: String = ""
    var doctorName: String = ""
    var comments: String?

    init(testName: String, testResults: String, normalRange: String, unit: String, labName: String, doctorName: String, date: Date = Date(), comments: String? = nil) {
        self.testName = testName
        self.testResults = testResults
        self.normalRange = normalRange
        self.unit = unit
        self.labName = labName
        self.doctorName = doctorName
        self.date = date
        self.comments = comments
    }

    enum CodingKeys: String, CodingKey {
        case id
        case date
        case testName = "test_name"
        case testResults = "test_results"
        case normalRange = "normal_range"
        case unit
        case labName = "lab_name"
        case doctorName = "doctor_name"
        case comments
    }

    // Hashable conformance
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    // Equatable conformance
    static func == (lhs: LabReport, rhs: LabReport) -> Bool {
        return lhs.id == rhs.id
    }
}

// MARK: - Trends Models
struct TrendDataPoint: Codable, Identifiable {
    let id = UUID()
    let period: String?
    let date: String?
    let year: Int?
    let month: Int?
    let quarter: Int?
    let value: Double?
    let status: String?
    let count: Int?
    
    enum CodingKeys: String, CodingKey {
        case period, date, year, month, quarter, value, status, count
    }
}

struct TestTrends: Codable {
    let daily: [TrendDataPoint]
    let monthly: [TrendDataPoint]
    let quarterly: [TrendDataPoint]
    let yearly: [TrendDataPoint]
}

struct TestTrendsResponse: Codable {
    let testName: String
    let currentValue: String?
    let currentUnit: String?
    let normalRange: String?
    let lastTested: String?
    let currentStatus: String?
    let trends: TestTrends
}
