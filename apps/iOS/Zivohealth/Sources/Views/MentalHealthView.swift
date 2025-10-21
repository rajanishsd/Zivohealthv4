import SwiftUI
import Charts

struct MentalHealthView: View {
    @StateObject private var service = MentalHealthService.shared
    @State private var selectedRange: RangeTab = .week
    @State private var showLogSheet = false
    @State private var selectedOverlays: Set<OverlayMetric> = [.exercise]
    
    
    private let xAxisFormatter: DateFormatter = {
        let df = DateFormatter()
        df.dateFormat = "dd-MMM"
        return df
    }()
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    // Scrollable header
                    MentalHealthHeaderView(topInset: geometry.safeAreaInsets.top)
                    
                    VStack(spacing: 16) {
                        header
                        logButton
                        rangeTabs
                        chartCard
                        tabsCard
                        Spacer(minLength: 80)
                    }
                    .padding(.horizontal)
                    .padding(.top, 8)
                }
            }
            .background(Color(.systemGroupedBackground))
            .fullScreenCover(isPresented: $showLogSheet) {
                LogMoodSheet()
            }
            .onAppear {
                // Only load data if user is authenticated
                guard NetworkService.shared.isAuthenticated() else {
                    print("⚠️ [MentalHealthView] User not authenticated - skipping data load")
                    return
                }
                
                print("🚨🚨🚨 [MentalHealthView] ON APPEAR CALLED 🚨🚨🚨")
                service.refreshDictionariesFromAPI()
                service.loadRollup(rangeDays: selectedRange.defaultDays)
                // Load initial overlay vitals for the default selection
                print("🚨🚨🚨 [MentalHealthView] Loading initial overlay vitals for: \(selectedOverlays.map { $0.title }) 🚨🚨🚨")
                print("🚨🚨🚨 [MentalHealthView] Selected range: \(selectedRange), days: \(selectedRange.defaultDays) 🚨🚨🚨")
                service.loadOverlayVitals(selected: selectedOverlays, days: selectedRange.defaultDays, granularity: granularityForRange(selectedRange))
            }
            .onChange(of: selectedRange) { newValue in
                print("🚨🚨🚨 [MentalHealthView] Range changed to: \(newValue) 🚨🚨🚨")
                service.loadRollup(rangeDays: newValue.defaultDays)
                // Reload overlay vitals when range changes with appropriate granularity
                service.loadOverlayVitals(selected: selectedOverlays, days: newValue.defaultDays, granularity: granularityForRange(newValue))
            }
            .ignoresSafeArea(.container, edges: .top)
        }
        .navigationBarHidden(true)
    }
    
    private func granularityForRange(_ range: RangeTab) -> String {
        switch range {
        case .week:
            return "daily"      // Weekly data: show daily aggregations
        case .month:
            return "weekly"     // Monthly data: show weekly aggregations
        case .sixMonths:
            return "monthly"    // 6 months data: show monthly aggregations
        case .year:
            return "quarterly"  // Yearly data: show quarterly aggregations
        }
    }
    
    private func twoLineLabel(for score: Int) -> String {
        let label = service.labelForScore(score)
        // Insert line break at first space to form two-line labels when possible
        if let idx = label.firstIndex(of: " ") {
            let first = label[..<idx]
            let second = label[label.index(after: idx)...]
            return String(first + "\n" + second)
        }
        return label
    }
    
    // MARK: - Time helpers for x-axis aggregation
    private func anchorDate(_ date: Date, for range: RangeTab) -> Date {
        let cal = Calendar.current
        switch range {
        case .week:
            return cal.startOfDay(for: date)
        case .month:
            return cal.dateInterval(of: .weekOfYear, for: date)?.start ?? cal.startOfDay(for: date)
        case .sixMonths:
            return cal.dateInterval(of: .month, for: date)?.start ?? cal.startOfDay(for: date)
        case .year:
            let comps = cal.dateComponents([.year, .month], from: date)
            let month = comps.month ?? 1
            let quarterStartMonth = ((month - 1) / 3) * 3 + 1
            var c = DateComponents()
            c.year = comps.year
            c.month = quarterStartMonth
            c.day = 1
            return cal.startOfDay(for: cal.date(from: c) ?? date)
        }
    }
    
    private func pad(domainStart: Date, domainEnd: Date, for range: RangeTab) -> ClosedRange<Date> {
        let cal = Calendar.current
        switch range {
        case .week:
            let start = cal.date(byAdding: .day, value: -1, to: domainStart) ?? domainStart
            let end = cal.date(byAdding: .day, value: 2, to: domainEnd) ?? domainEnd
            return start...end
        case .month:
            let start = cal.date(byAdding: .weekOfYear, value: -1, to: domainStart) ?? domainStart
            let end = cal.date(byAdding: .weekOfYear, value: 1, to: domainEnd) ?? domainEnd
            return start...end
        case .sixMonths:
            let start = cal.date(byAdding: .month, value: -1, to: domainStart) ?? domainStart
            let end = cal.date(byAdding: .month, value: 1, to: domainEnd) ?? domainEnd
            return start...end
        case .year:
            let start = cal.date(byAdding: .month, value: -3, to: domainStart) ?? domainStart
            let end = cal.date(byAdding: .month, value: 3, to: domainEnd) ?? domainEnd
            return start...end
        }
    }
    
    private func tickDates(for domain: ClosedRange<Date>, range: RangeTab) -> [Date] {
        let cal = Calendar.current
        var ticks: [Date] = []
        var d = anchorDate(domain.lowerBound, for: range)
        while d <= domain.upperBound {
            ticks.append(d)
            switch range {
            case .week:
                d = cal.date(byAdding: .day, value: 2, to: d) ?? d
            case .month:
                d = cal.date(byAdding: .weekOfYear, value: 1, to: d) ?? d
            case .sixMonths:
                d = cal.date(byAdding: .month, value: 1, to: d) ?? d
            case .year:
                d = cal.date(byAdding: .month, value: 3, to: d) ?? d
            }
        }
        return ticks
    }
    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .foregroundColor(.purple)
                Text("Today's Mental Health")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text(Date(), style: .date)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if let latest = service.latestEntryToday {
                HStack(spacing: 8) {
                    Text(service.labelForScore(latest.pleasantnessScore))
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    Spacer()
                    Text(latest.recordedAt, style: .time)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .accessibilityLabel("Today's mental health: \(latest.pleasantnessLabel)")
            } else if let todayPoint = service.dailyPoints.first(where: { Calendar.current.isDateInToday($0.date) }) {
                HStack(spacing: 8) {
                    Text(service.labelForScore(todayPoint.score))
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    Spacer()
                    Text("Today")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .accessibilityLabel("Today's mental health: \(todayPoint.label)")
            } else {
                Text("No mental health entry today")
                    .foregroundColor(.secondary)
            }
        }
        .cardStyle()
    }
    
    private var logButton: some View {
        Button(action: { showLogSheet = true }) {
            HStack(spacing: 8) {
                Image(systemName: "plus.circle.fill")
                    .font(.title3)
                Text("Log Mood")
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.green)
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }
    
    private var rangeTabs: some View {
        Picker("Range", selection: $selectedRange) {
            Text("W").tag(RangeTab.week)
            Text("M").tag(RangeTab.month)
            Text("6M").tag(RangeTab.sixMonths)
            Text("Y").tag(RangeTab.year)
        }
        .pickerStyle(.segmented)
    }
    
    private var chartCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundColor(.purple)
                Text("Mental Health")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            // X domain will be computed only when we have data
            
            if service.dailyPoints.isEmpty {
                Text("No data for selected range")
                    .foregroundColor(.secondary)
            } else {
                    if #available(iOS 16.0, *) {
                        // Compute a shared X domain across both charts by selected granularity
                        let xDomain: ClosedRange<Date> = {
                            var dates: [Date] = service.dailyPoints.map { anchorDate($0.date, for: selectedRange) }
                            let overlayDates = service.overlaySeriesByMetric.values.flatMap { series in series.map { anchorDate($0.date, for: selectedRange) } }
                            dates.append(contentsOf: overlayDates)
                            let startBase = dates.min() ?? Date()
                            let endBase = dates.max() ?? startBase
                            return pad(domainStart: startBase, domainEnd: endBase, for: selectedRange)
                        }()
                        let ticks = tickDates(for: xDomain, range: selectedRange)
                        VStack(spacing: 16) {
                            // Mental Health Chart
                            VStack(alignment: .leading, spacing: 8) {
                                Chart {
                                    ForEach(service.dailyPoints, id: \.id) { point in
                                        PointMark(
                                            x: .value("Date", Calendar.current.startOfDay(for: point.date), unit: .day),
                                            y: .value("Score", point.score)
                                        )
                                        .foregroundStyle(.purple)
                                        .symbol(.circle)
                                        .symbolSize(60)
                                    }
                                }
                                .chartXAxis {
                                    AxisMarks(values: ticks) { value in
                                        AxisGridLine()
                                        AxisValueLabel {
                                            if let date = value.as(Date.self) {
                                                switch selectedRange {
                                                case .week:
                                                    Text(xAxisFormatter.string(from: date))
                                                case .month:
                                                    Text(date, format: .dateTime.day().month(.abbreviated))
                                                case .sixMonths:
                                                    Text(date, format: .dateTime.month(.abbreviated))
                                                case .year:
                                                    Text(date, format: .dateTime.month(.abbreviated))
                                                }
                                            }
                                        }
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                    }
                                }
                                .chartXScale(domain: xDomain)
                                .chartYScale(domain: -3...3)
                                .chartYAxis {
                                    // Show edge and center labels for better vertical spacing
                                    AxisMarks(position: .trailing, values: [-3, 0, 3]) { value in
                                        AxisGridLine()
                                        AxisValueLabel {
                                            if let v = value.as(Int.self) {
                                                Text(twoLineLabel(for: v))
                                                    .multilineTextAlignment(.trailing)
                                                    .lineSpacing(2)
                                            }
                                        }
                                    }
                                }
                                .frame(height: 180)
                            }
                            
                            // Vitals Charts (always visible)
                            VStack(alignment: .leading, spacing: 12) {
                                    HStack {
                                        Image(systemName: "waveform.path.ecg")
                                            .foregroundColor(.orange)
                                        Text("Vitals Overlay")
                                            .font(.headline)
                                            .fontWeight(.semibold)
                                        Spacer()
                                        // Show selected overlay types
                                        HStack(spacing: 8) {
                                            ForEach(Array(selectedOverlays), id: \.self) { metric in
                                                HStack(spacing: 4) {
                                                    Circle()
                                                        .fill(metric.color)
                                                        .frame(width: 8, height: 8)
                                                    Text(metric.title)
                                                        .font(.caption)
                                                        .foregroundColor(.secondary)
                                                }
                                            }
                                        }
                                    }
                                    
                                    Chart {
                                        // Exercise line
                                        if let series = service.overlaySeriesByMetric[.exercise] {
                                            ForEach(Array(series.enumerated()), id: \.offset) { _, pt in
                                                LineMark(
                                                    x: .value("Date", anchorDate(pt.date, for: selectedRange), unit: .day),
                                                    y: .value("Exercise", pt.value)
                                                )
                                                .interpolationMethod(.linear)
                                                .foregroundStyle(by: .value("Series", "Exercise"))
                                                .symbol(by: .value("Series", "Exercise"))
                                                .foregroundStyle(OverlayMetric.exercise.color)
                                                .lineStyle(StrokeStyle(lineWidth: 2))
                                            }
                                        }
                                        // Sleep line
                                        if let series = service.overlaySeriesByMetric[.sleep] {
                                            ForEach(Array(series.enumerated()), id: \.offset) { _, pt in
                                                LineMark(
                                                    x: .value("Date", anchorDate(pt.date, for: selectedRange), unit: .day),
                                                    y: .value("Sleep", pt.value)
                                                )
                                                .interpolationMethod(.linear)
                                                .foregroundStyle(by: .value("Series", "Sleep"))
                                                .symbol(by: .value("Series", "Sleep"))
                                                .foregroundStyle(OverlayMetric.sleep.color)
                                                .lineStyle(StrokeStyle(lineWidth: 2, dash: [4,2]))
                                            }
                                        }
                                        // Heart Rate hanging range bars (min/max) with average dot
                                        if let series = service.overlaySeriesByMetric[.heartRate] {
                                            ForEach(Array(series.enumerated()), id: \.offset) { _, pt in
                                                let xVal = anchorDate(pt.date, for: selectedRange)
                                                let minV = pt.min ?? pt.value
                                                let maxV = pt.max ?? pt.value
                                                let hasRange = (pt.min != nil || pt.max != nil) && minV != maxV
                                                if hasRange {
                                                    RectangleMark(
                                                        x: .value("Date", xVal, unit: .day),
                                                        yStart: .value("Min HR", minV),
                                                        yEnd: .value("Max HR", maxV),
                                                        width: 6
                                                    )
                                                    .foregroundStyle(OverlayMetric.heartRate.color.opacity(0.8))
                                                    .cornerRadius(3)

                                                    PointMark(
                                                        x: .value("Date", xVal, unit: .day),
                                                        y: .value("Avg HR", pt.value)
                                                    )
                                                    .foregroundStyle(.white)
                                                    .symbolSize(24)
                                                    .symbol(.circle)
                                                } else {
                                                    // No min/max range available: show a visible red dot
                                                    PointMark(
                                                        x: .value("Date", xVal, unit: .day),
                                                        y: .value("HR", pt.value)
                                                    )
                                                    .foregroundStyle(OverlayMetric.heartRate.color)
                                                    .symbol(.circle)
                                                    .symbolSize(32)
                                                }
                                            }
                                        }
                                    }
                                    .chartXAxis {
                                        AxisMarks(values: ticks) { value in
                                            AxisGridLine()
                                            AxisValueLabel {
                                                if let date = value.as(Date.self) {
                                                    switch selectedRange {
                                                    case .week:
                                                        Text(xAxisFormatter.string(from: date))
                                                    case .month:
                                                        Text(date, format: .dateTime.day().month(.abbreviated))
                                                    case .sixMonths:
                                                        Text(date, format: .dateTime.month(.abbreviated))
                                                    case .year:
                                                        Text(date, format: .dateTime.month(.abbreviated))
                                                    }
                                                }
                                            }
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                        }
                                    }
                                    .chartXScale(domain: xDomain)
                                    .frame(height: 180)
                                }
                            }
                        .frame(height: 380)
                    } else {
                        VStack(spacing: 8) {
                            Image(systemName: "chart.xyaxis.line")
                                .font(.title2)
                                .foregroundColor(.secondary)
                            Text("Charts are available on iOS 16+")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .frame(height: 220)
                    }
            }
            
            // Overlay selector chips
            HStack(spacing: 8) {
                ForEach(OverlayMetric.allCases, id: \.self) { metric in
                    let isOn = selectedOverlays.contains(metric)
                    Text(metric.title)
                        .font(.caption)
                        .fontWeight(.medium)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(isOn ? metric.color.opacity(0.15) : Color.gray.opacity(0.12))
                        .foregroundColor(isOn ? metric.color : .secondary)
                        .cornerRadius(8)
                        .onTapGesture {
                            print("🚨🚨🚨 [MentalHealthView] Overlay metric tapped: \(metric.title) (was \(isOn ? "on" : "off")) 🚨🚨🚨")
                            if isOn { selectedOverlays.remove(metric) } else { selectedOverlays.insert(metric) }
                            print("🚨🚨🚨 [MentalHealthView] Selected overlays now: \(selectedOverlays.map { $0.title }) 🚨🚨🚨")
                            // Fetch overlay vitals for the selected range with appropriate granularity
                            service.loadOverlayVitals(selected: selectedOverlays, days: selectedRange.defaultDays, granularity: granularityForRange(selectedRange))
                        }
                }
                Spacer()
            }
        }
        .cardStyle()
    }
    
    private var tabsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Sections", selection: $internalTab) {
                Text("Feelings").tag(InternalTab.feelings)
                Text("Impacts").tag(InternalTab.impacts)
            }
            .pickerStyle(.segmented)
            
            Group {
                switch internalTab {
                case .feelings:
                    feelingsView
                case .impacts:
                    impactsView
                }
            }
        }
        .cardStyle()
    }
    
    @State private var internalTab: InternalTab = .feelings
    
    private var feelingsView: some View {
        // Bubble chart sized by authoritative backend counts to avoid flicker
        let counts: [(String, Int)] = service.feelingsCounts.isEmpty ? {
            var map: [String: Int] = [:]
            for f in service.dailyPoints.flatMap({ $0.feelings }) { map[f, default: 0] += 1 }
            return map.sorted { $0.value > $1.value }
        }() : service.feelingsCounts
        let maxCount = max(counts.first?.1 ?? 0, 1)
        return VStack(alignment: .leading, spacing: 12) {
            if counts.isEmpty {
                Text("No data")
                    .foregroundColor(.secondary)
            } else {
                CirclePackView(
                    items: counts.map { CirclePackItem(label: $0.0, count: $0.1) }
                )
                .frame(height: 260)
            }
        }
    }
    
    private var impactsView: some View {
        // Bubble chart for impacts using backend counts when available
        let counts: [(String, Int)] = service.impactsCounts.isEmpty ? {
            var map: [String: Int] = [:]
            for i in service.dailyPoints.flatMap({ $0.impacts }) { map[i, default: 0] += 1 }
            return map.sorted { $0.value > $1.value }
        }() : service.impactsCounts
        return VStack(alignment: .leading, spacing: 12) {
            if counts.isEmpty {
                Text("No data")
                    .foregroundColor(.secondary)
            } else {
                CirclePackView(
                    items: counts.map { CirclePackItem(label: $0.0, count: $0.1) }
                )
                .frame(height: 260)
            }
        }
    }
}

// MARK: - Simple circle packing layout
private struct CirclePackItem: Identifiable, Hashable {
    let id = UUID()
    let label: String
    let count: Int
}

private struct CirclePackView: View {
    let items: [CirclePackItem]
    var colors: [Color] = [.purple, .blue, .orange, .green, .pink, .red, .teal, .indigo, .brown, .mint]

    var body: some View {
        GeometryReader { geo in
            let sorted = items.sorted { $0.count > $1.count }
            let maxCount = max(sorted.first?.count ?? 1, 1)
            let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
            ZStack {
                ForEach(Array(sorted.enumerated()), id: \.1.id) { idx, item in
                    let scale = max(0.4, CGFloat(item.count) / CGFloat(maxCount))
                    let radius = 30 + 50 * scale
                    // Place circles in concentric rings around center
                    let ring = Int(sqrt(Double(idx)))
                    let angle = Double(idx) * 137.508  // golden angle for spread
                    let ringRadius = CGFloat(20 * ring) + radius
                    let x = center.x + ringRadius * CGFloat(cos(angle * .pi / 180))
                    let y = center.y + ringRadius * CGFloat(sin(angle * .pi / 180))
                    let color = colors[idx % colors.count]
                    VStack(spacing: 2) {
                        ZStack {
                            Circle()
                                .fill(color.opacity(0.12))
                                .frame(width: radius * 2, height: radius * 2)
                            VStack(spacing: 2) {
                                Text(item.label)
                                    .font(.system(size: max(12, 14 * scale), weight: .semibold))
                                    .foregroundColor(color)
                                    .multilineTextAlignment(.center)
                                    .lineLimit(2)
                                    .frame(width: radius * 2 - 12)
                                Text("\(item.count)")
                                    .font(.system(size: max(10, 12 * scale)))
                                    .foregroundColor(color.opacity(0.9))
                            }
                        }
                    }
                    .position(x: min(max(radius, x), geo.size.width - radius), y: min(max(radius, y), geo.size.height - radius))
                    .accessibilityLabel("\(item.label) \(item.count)")
                }
            }
        }
    }
}
// MARK: - Supporting Types

private enum InternalTab: Hashable { case feelings, impacts }

private enum RangeTab: Hashable { case week, month, sixMonths, year
    var defaultDays: Int {
        switch self {
        case .week: return 7
        case .month: return 30
        case .sixMonths: return 180
        case .year: return 365
        }
    }
}

// OverlayMetric now defined in MentalHealthService.swift for shared use

// Simple tags view
struct WrapTagsView: View {
    let tags: [String]
    var body: some View {
        if tags.isEmpty {
            Text("No data")
                .foregroundColor(.secondary)
        } else {
            FlowLayout(alignment: .leading, spacing: 8) {
                ForEach(tags.sorted(), id: \.self) { tag in
                    Text(tag)
                        .font(.caption)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Color.gray.opacity(0.12))
                        .cornerRadius(8)
                }
            }
        }
    }
}

// Lightweight flow layout for tags
private struct FlowLayout<Content: View>: View {
    let alignment: HorizontalAlignment
    let spacing: CGFloat
    @ViewBuilder let content: Content
    
    init(alignment: HorizontalAlignment = .leading, spacing: CGFloat = 8, @ViewBuilder content: () -> Content) {
        self.alignment = alignment
        self.spacing = spacing
        self.content = content()
    }
    
    var body: some View {
        LazyVStack(alignment: alignment, spacing: spacing) {
            content
        }
    }
}

// MARK: - Log Sheet

private struct LogMoodSheet: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var service = MentalHealthService.shared
    @State private var entryType: MentalHealthEntryType = .emotionNow
    @State private var pleasantness: Int = 1
    @State private var selectedFeelings = Set<String>()
    @State private var selectedImpacts = Set<String>()
    @State private var notes: String = ""
    @State private var step: Int = 0 // 0: Type, 1: Pleasantness, 2: Feelings, 3: Impacts

    private var canSave: Bool {
        return !selectedFeelings.isEmpty && !selectedImpacts.isEmpty
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Progress bar
                ProgressView(value: Double(step + 1), total: 4)
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
                    .padding(.horizontal)
                    .padding(.top, 8)
                
                // Step content
                Group {
                    switch step {
                    case 0:
                        Form {
                            Section(header: Text("Type")) {
                                Picker("Entry Type", selection: $entryType) {
                                    Text("How you feel right now").tag(MentalHealthEntryType.emotionNow)
                                    Text("How you felt today").tag(MentalHealthEntryType.moodToday)
                                }
                                .pickerStyle(.inline)
                            }
                        }
                    case 1:
                        Form {
                            Section(header: Text("Pleasantness")) {
                                Stepper(value: $pleasantness, in: -3...3) {
                                    Text("\(service.labelForScore(pleasantness)) (\(pleasantness))")
                                }
                            }
                        }
                    case 2:
                        // Full-page list for Feelings (no placeholder container)
                        MultiSelectList(all: service.mentalhealth_feelings, selected: $selectedFeelings)
                            .listStyle(.insetGrouped)
                    default:
                        // Full-page list for Impacts (no placeholder container)
                        MultiSelectList(all: service.mentalhealth_impact, selected: $selectedImpacts)
                            .listStyle(.insetGrouped)
                    }
                }
                
                // Navigation controls
                HStack {
                    Button("Back") {
                        if step > 0 { step -= 1 }
                    }
                    .disabled(step == 0)
                    Spacer()
                    if step < 3 {
                        Button("Next") {
                            if step == 2 {
                                // Require at least one feeling before proceeding
                                if selectedFeelings.isEmpty { return }
                            }
                            step += 1
                        }
                        .disabled(step == 2 && selectedFeelings.isEmpty)
                            .buttonStyle(.borderedProminent)
                    } else {
                        Button("Save") { save() }
                            .disabled(!canSave)
                            .buttonStyle(.borderedProminent)
                    }
                }
                .padding()
            }
            .navigationTitle("Log Mood")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
            }
        }
    }
    
    private func save() {
        let entry = MentalHealthEntry(
            id: UUID(),
            userId: "me",
            recordedAt: Date(),
            entryType: entryType,
            pleasantnessScore: pleasantness,
            pleasantnessLabel: service.labelForScore(pleasantness),
            feelings: Array(selectedFeelings),
            impacts: Array(selectedImpacts),
            notes: notes.isEmpty ? nil : notes
        )
        service.createEntryViaAPI(from: entry)
        service.saveEntry(entry)
        dismiss()
    }
}

private struct MultiSelectList: View {
    let all: [String]
    @Binding var selected: Set<String>
    var body: some View {
        List {
            ForEach(all, id: \.self) { item in
                HStack {
                    Text(item)
                    Spacer()
                    if selected.contains(item) {
                        Image(systemName: "checkmark").foregroundColor(.accentColor)
                    }
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    if selected.contains(item) { selected.remove(item) } else { selected.insert(item) }
                }
            }
        }
        .listStyle(.plain)
    }
}

// MARK: - Mental Health Header
struct MentalHealthHeaderView: View {
    let topInset: CGFloat
    @Environment(\.dismiss) private var dismiss
    
    private var brandRedGradient: Gradient {
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top spacer for status bar
            Color.clear
                .frame(height: topInset)
            
            // Card content with back button
            ZStack(alignment: .topLeading) {
                LinearGradient(
                    gradient: brandRedGradient,
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                
                ZStack {
                    // Centered title and subtitle with offset to move down
                    VStack(spacing: 4) {
                        Text("Mental Health")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        Text("Track your mood and mental wellness")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                    .offset(y: 15)
                    
                    // Back button on the left, vertically centered
                    HStack {
                        Button(action: {
                            dismiss()
                        }) {
                            Image(systemName: "arrow.backward")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundColor(.white)
                        }
                        .padding(.leading, 20)
                        
                        Spacer()
                    }
                    .offset(y: 10)
                    
                    // Brain icon on the right, vertically centered
                    HStack {
                        Spacer()
                        
                        Image(systemName: "brain.head.profile")
                            .font(.system(size: 40))
                            .foregroundColor(.white.opacity(0.9))
                            .padding(.trailing, 20)
                    }
                }
                .padding(.vertical, 20)
            }
            .frame(height: 110)
            .cornerRadius(20)
            .padding(.horizontal, 16)
            .padding(.top, 8)
        }
        .frame(height: 110 + topInset + 8)
        .ignoresSafeArea(.container, edges: .top)
    }
}


