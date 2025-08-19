import Foundation

struct HealthMetric: Identifiable, Codable, Hashable, Equatable {
    let id: String = UUID().uuidString
    var date: Date = .init()
    var type: String = ""
    var value: Double = 0.0
    var unit: String = ""
    var notes: String?

    init(type: String, value: Double, unit: String, date: Date = Date(), notes: String? = nil) {
        self.type = type
        self.value = value
        self.unit = unit
        self.date = date
        self.notes = notes
    }

    enum CodingKeys: String, CodingKey {
        case id
        case date
        case type
        case value
        case unit
        case notes
    }

    // Hashable conformance
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    // Equatable conformance
    static func == (lhs: HealthMetric, rhs: HealthMetric) -> Bool {
        return lhs.id == rhs.id
    }
}
