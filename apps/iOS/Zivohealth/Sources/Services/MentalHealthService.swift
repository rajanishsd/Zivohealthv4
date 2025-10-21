import Foundation
import Combine
import SwiftUI

// MARK: - Models

enum MentalHealthEntryType: String, Codable {
    case emotionNow = "emotion_now"
    case moodToday = "mood_today"
}

// Overlay metrics shared with UI
enum OverlayMetric: CaseIterable, Hashable {
    case exercise, sleep, heartRate
    var title: String {
        switch self {
        case .exercise: return "Exercise Minutes"
        case .sleep: return "Sleep"
        case .heartRate: return "Heart Rate"
        }
    }
    var color: Color {
        switch self {
        case .exercise: return .orange
        case .sleep: return .blue
        case .heartRate: return .red
        }
    }
    var apiMetricTypeString: String {
        switch self {
        case .exercise: return "Workout Duration"
        case .sleep: return "Sleep"
        case .heartRate: return "Heart Rate"
        }
    }
}

struct MentalHealthEntry: Identifiable, Codable, Hashable {
    let id: UUID
    let userId: String
    let recordedAt: Date
    let entryType: MentalHealthEntryType
    let pleasantnessScore: Int // -3 ... +3
    let pleasantnessLabel: String // very_unpleasant .. very_pleasant
    let feelings: [String]
    let impacts: [String]
    let notes: String?
}

struct MentalHealthDailyPoint: Identifiable, Hashable {
    let id = UUID()
    let date: Date
    let score: Int // -3 ... +3
    let label: String
    let feelings: [String]
    let impacts: [String]
}

// Represents a single bar segment in the stacked vitals chart
struct OverlayBarPoint: Identifiable, Hashable {
    let id = UUID()
    let date: Date
    let metric: OverlayMetric
    let value: Double
}

// MARK: - Service

final class MentalHealthService: ObservableObject {
    static let shared = MentalHealthService()

    // Published state for the UI
    @Published private(set) var dailyPoints: [MentalHealthDailyPoint] = []
    @Published private(set) var overlayPoints: [(date: Date, value: Double, min: Double?, max: Double?)] = []
    @Published private(set) var overlayStackedPoints: [OverlayBarPoint] = []
    @Published private(set) var overlaySeriesByMetric: [OverlayMetric: [(date: Date, value: Double, min: Double?, max: Double?)]] = [:]
    @Published private(set) var feelingsCounts: [(name: String, count: Int)] = []
    @Published private(set) var impactsCounts: [(name: String, count: Int)] = []
    @Published private(set) var latestEntryToday: MentalHealthEntry?
    @Published private(set) var errorMessage: String?

    // Dictionaries loaded from backend
    @Published private(set) var mentalhealth_feelings: [String] = []
    @Published private(set) var mentalhealth_impact: [String] = []
    @Published private(set) var pleasantnessMap: [Int: String] = [:]

    private var cancellables = Set<AnyCancellable>()

    private init() {}

    // MARK: - Public API (placeholder implementations)

    func loadRollup(rangeDays: Int) {
        // Map days to range param expected by backend
        let range: String
        switch rangeDays {
        case ..<8: range = "W"
        case 8..<60: range = "M"
        case 60..<365: range = "6M"
        default: range = "Y"
        }
        MentalHealthAPIService.shared.getRollup(range: range)
            .sink(receiveCompletion: { completion in
                if case .failure = completion {
                    self.dailyPoints = []
                }
            }, receiveValue: { resp in
                let iso = ISO8601DateFormatter()
                let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd"
                let points: [MentalHealthDailyPoint] = resp.data_points.compactMap { p in
                    let d = iso.date(from: p.date) ?? df.date(from: p.date)
                    guard let date = d else { return nil }
                    return MentalHealthDailyPoint(
                        date: date,
                        score: p.score,
                        label: self.labelForScore(p.score),
                        feelings: p.feelings,
                        impacts: p.impacts
                    )
                }
                self.dailyPoints = points
                if let f = resp.feelings_counts { self.feelingsCounts = f.map { ($0.name, $0.count) } }
                if let i = resp.impacts_counts { self.impactsCounts = i.map { ($0.name, $0.count) } }
            })
            .store(in: &cancellables)
    }

    func loadOverlayVitals(selected: Set<OverlayMetric>, days: Int, granularity: String = "daily") {
        let types = selected.map { $0.apiMetricTypeString }
        let needsHRQuarterlyFallback = selected.contains(.heartRate) && granularity == "quarterly"
        let effectiveGranularity = needsHRQuarterlyFallback ? "monthly" : granularity
        print("🚨🚨🚨 [MentalHealthService] loadOverlayVitals called with: \(types), days: \(days), granularity: \(granularity) (effective: \(effectiveGranularity)) 🚨🚨🚨")
        guard !types.isEmpty else {
            print("🚨🚨🚨 [MentalHealthService] No types selected, clearing overlayPoints 🚨🚨🚨")
            self.overlayPoints = [];
            return
        }
        MentalHealthAPIService.shared.fetchVitalsCharts(metricTypes: types, days: days, granularity: effectiveGranularity)
            .sink(receiveCompletion: { completion in
                if case .failure(let error) = completion {
                    print("❌ [MentalHealthService] Failed to fetch overlay vitals: \(error)")
                    // Clear series on failure so UI does not show stale data
                    self.overlaySeriesByMetric = [:]
                } else {
                    print("✅ [MentalHealthService] Successfully completed overlay vitals fetch")
                }
            }, receiveValue: { resp in
                print("🔄 [MentalHealthService] Received vitals response with \(resp.charts.count) charts")
                guard !resp.charts.isEmpty else {
                    print("⚠️ [MentalHealthService] No charts in response, clearing overlay points")
                    self.overlayPoints = []
                    self.overlayStackedPoints = []
                    return
                }

                let iso = ISO8601DateFormatter(); let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd"

                if let first = resp.charts.first {
                    self.overlayPoints = first.data_points.compactMap { p in
                        let d = iso.date(from: p.date) ?? df.date(from: p.date)
                        guard let date = d, let value = p.value else { return nil }
                        return (date: date, value: value, min: p.min_value, max: p.max_value)
                    }
                    print("✅ [MentalHealthService] Processed \(self.overlayPoints.count) overlay points (first chart)")
                }

                var stacked: [OverlayBarPoint] = []
                var seriesByMetric: [OverlayMetric: [(date: Date, value: Double, min: Double?, max: Double?)]] = [:]
                for chart in resp.charts {
                    let metricMatch = OverlayMetric.allCases.first { $0.apiMetricTypeString == chart.metric_type }
                    guard let metric = metricMatch else { continue }
                    let transformed: [(date: Date, value: Double, min: Double?, max: Double?)] = chart.data_points.compactMap { p in
                        let d = iso.date(from: p.date) ?? df.date(from: p.date)
                        guard let date = d, let value = p.value else { return nil }
                        return (date: date, value: value, min: p.min_value, max: p.max_value)
                    }
                    seriesByMetric[metric] = transformed
                    for t in transformed { stacked.append(OverlayBarPoint(date: t.date, metric: metric, value: t.value)) }
                }
                self.overlayStackedPoints = stacked.sorted { $0.date < $1.date }

                // If we requested quarterly but used monthly as effective granularity for Heart Rate,
                // aggregate monthly into quarterly (min of mins, max of maxs, avg of values).
                if needsHRQuarterlyFallback, var hr = seriesByMetric[.heartRate] {
                    let cal = Calendar.current
                    func quarterStart(_ d: Date) -> Date {
                        let comps = cal.dateComponents([.year, .month], from: d)
                        let m = comps.month ?? 1
                        let qStartMonth = ((m - 1) / 3) * 3 + 1
                        var c = DateComponents()
                        c.year = comps.year
                        c.month = qStartMonth
                        c.day = 1
                        return cal.date(from: c) ?? d
                    }
                    let grouped = Dictionary(grouping: hr, by: { quarterStart($0.date) })
                    var aggregated: [(date: Date, value: Double, min: Double?, max: Double?)] = []
                    for (qStart, pts) in grouped {
                        let values = pts.map { $0.value }
                        let avg = values.reduce(0, +) / Double(max(values.count, 1))
                        let mins: [Double] = pts.compactMap { $0.min ?? $0.value }
                        let maxs: [Double] = pts.compactMap { $0.max ?? $0.value }
                        let minVal = mins.min()
                        let maxVal = maxs.max()
                        aggregated.append((date: qStart, value: avg, min: minVal, max: maxVal))
                    }
                    hr = aggregated.sorted { $0.date < $1.date }
                    seriesByMetric[.heartRate] = hr
                }

                self.overlaySeriesByMetric = seriesByMetric
                print("✅ [MentalHealthService] Prepared \(self.overlayStackedPoints.count) stacked overlay bar points")
            })
            .store(in: &cancellables)
    }

    func saveEntry(_ entry: MentalHealthEntry) {
        // For now, keep only in-memory latest entry today; integrate with backend later
        if Calendar.current.isDateInToday(entry.recordedAt) {
            self.latestEntryToday = entry
        }
    }

    // MARK: - Helpers

    func labelForScore(_ score: Int) -> String {
        if let label = pleasantnessMap[score] { return label }
        // Fallback if dictionary not yet loaded
        switch score {
        case -3: return "Very Unpleasant"
        case -2: return "Unpleasant"
        case -1: return "Slightly Unpleasant"
        case 0: return "Neutral"
        case 1: return "Slightly Pleasant"
        case 2: return "Pleasant"
        default: return "Very Pleasant"
        }
    }
}

// MARK: - API integration
import Combine

extension MentalHealthService {
    func refreshDictionariesFromAPI() {
        MentalHealthAPIService.shared.fetchDictionaries()
            .sink(receiveCompletion: { _ in }, receiveValue: { resp in
                self.mentalhealth_feelings = resp.mentalhealth_feelings
                self.mentalhealth_impact = resp.mentalhealth_impact
                if let list = resp.mentalhealth_pleasantness {
                    var map: [Int: String] = [:]
                    for p in list { map[p.score] = p.label }
                    self.pleasantnessMap = map
                }
            })
            .store(in: &cancellables)
    }
    
    func createEntryViaAPI(from entry: MentalHealthEntry) {
        let iso = ISO8601DateFormatter()
        let payload = MentalHealthAPIService.EntryCreatePayload(
            recorded_at: iso.string(from: entry.recordedAt),
            entry_type: entry.entryType.rawValue,
            pleasantness_score: entry.pleasantnessScore,
            pleasantness_label: entry.pleasantnessLabel,
            feelings: entry.feelings,
            impacts: entry.impacts,
            notes: entry.notes
        )
        MentalHealthAPIService.shared.createEntry(payload)
            .sink(receiveCompletion: { _ in }, receiveValue: { _ in })
            .store(in: &cancellables)
    }
}


