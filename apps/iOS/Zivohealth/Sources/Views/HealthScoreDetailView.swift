import SwiftUI
import Combine

struct HealthScoreDetailView: View {
    @StateObject private var api = HealthScoreAPIService.shared
    @State private var scoreText: String = "--"
    @State private var reasons: [[String: Any]] = []
    @State private var actions: [[String: Any]] = []
    @State private var detail: [String: Any] = [:]
    @State private var cancellables = Set<AnyCancellable>()

    var body: some View {
        List {
            Section(header: Text("Overall")) {
                Text(scoreText)
                    .font(.system(size: 44, weight: .bold))
            }
            // Per-modality cards with meta and insights
            ModalitySection(
                title: "Vitals Today",
                driver: "Today’s vitals",
                modality: (detail["acute"] as? [String: Any])?["vitals_today"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Sleep Last Night",
                driver: "Last-night sleep",
                modality: (detail["acute"] as? [String: Any])?["sleep_last_night"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Activity Today",
                driver: "Today’s activity",
                modality: (detail["acute"] as? [String: Any])?["activity_today"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Biomarkers",
                driver: "Biomarkers",
                modality: (detail["chronic"] as? [String: Any])?["biomarkers"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Medications",
                driver: "Medications",
                modality: (detail["chronic"] as? [String: Any])?["medications"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Sleep (7d)",
                driver: "Sleep",
                modality: (detail["chronic"] as? [String: Any])?["sleep"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Activity (7d)",
                driver: "Activity",
                modality: (detail["chronic"] as? [String: Any])?["activity"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            ModalitySection(
                title: "Vitals (30d)",
                driver: "Vitals",
                modality: (detail["chronic"] as? [String: Any])?["vitals_30d"] as? [String: Any],
                reasons: reasons,
                actions: actions
            )
            // Omit Data Gaps section; individual cards will reflect missing states
        }
        .listStyle(InsetGroupedListStyle())
        .onAppear(perform: fetch)
    }

    private func fetch() {
        api.getToday()
            .receive(on: DispatchQueue.main)
            .sink(receiveCompletion: { _ in }, receiveValue: { json in
                if let s = json["overall"] as? Double {
                    scoreText = String(format: "%.0f", s)
                }
                if let d = json["detail"] as? [String: Any] {
                    detail = d
                    if let insights = d["insights"] as? [String: Any] {
                        if let rs = insights["reasons"] as? [[String: Any]] { reasons = rs }
                        if let acts = insights["actions"] as? [[String: Any]] { actions = acts }
                    }
                }
            })
            .store(in: &cancellables)
    }
}

private struct ModalitySection: View {
    let title: String
    let driver: String
    let modality: [String: Any]?
    let reasons: [[String: Any]]
    let actions: [[String: Any]]

    var body: some View {
        let filteredReasons = reasons.filter { ($0["driver"] as? String) == driver }
        let filteredActions = actions.filter { ($0["driver"] as? String) == driver }
        Section(header: Text(title)) {
            // Score row
            if let m = modality, let sc = (m["score"] as? NSNumber)?.doubleValue {
                HStack {
                    Text("Score")
                    Spacer()
                    Text(String(format: "%.0f", sc))
                        .fontWeight(.semibold)
                }
            }
            // Reasons
            if !filteredReasons.isEmpty {
                ForEach(filteredReasons.indices, id: \.self) { idx in
                    let item = filteredReasons[idx]
                    Text(item["message"] as? String ?? "")
                }
            }
            // Actions
            if !filteredActions.isEmpty {
                ForEach(filteredActions.indices, id: \.self) { idx in
                    let item = filteredActions[idx]
                    HStack {
                        Image(systemName: "chevron.right.circle.fill").foregroundColor(.blue)
                        Text((item["action"] as? String) ?? (item["message"] as? String) ?? "")
                            .fontWeight(.medium)
                    }
                }
            }
        }
    }
}
