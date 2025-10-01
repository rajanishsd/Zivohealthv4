import Foundation
import HealthKit

class HealthKitManager: ObservableObject {
    private let healthStore = HKHealthStore()
    
    @Published var isAuthorized = false
    @Published var healthMetrics: [HealthMetric] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    // Define the health data types we want to read
    private let healthDataTypes: Set<HKSampleType> = [
        HKQuantityType.quantityType(forIdentifier: .heartRate)!,
        HKQuantityType.quantityType(forIdentifier: .bloodPressureSystolic)!,
        HKQuantityType.quantityType(forIdentifier: .bloodPressureDiastolic)!,
        HKQuantityType.quantityType(forIdentifier: .bloodGlucose)!,
        HKQuantityType.quantityType(forIdentifier: .bodyTemperature)!,
        HKQuantityType.quantityType(forIdentifier: .bodyMass)!,
        HKQuantityType.quantityType(forIdentifier: .stepCount)!,
        HKQuantityType.quantityType(forIdentifier: .distanceWalkingRunning)!,
        HKQuantityType.quantityType(forIdentifier: .appleStandTime)!,
        HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned)!,
        HKQuantityType.quantityType(forIdentifier: .basalEnergyBurned)!,
        HKQuantityType.quantityType(forIdentifier: .flightsClimbed)!,
        HKObjectType.workoutType(),
        HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!
    ]
    
    init() {
        checkHealthKitAvailability()
    }
    
    private func checkHealthKitAvailability() {
        guard HKHealthStore.isHealthDataAvailable() else {
            errorMessage = "Health data is not available on this device"
            return
        }
        requestAuthorization()
    }
    
    func requestAuthorization() {
        healthStore.requestAuthorization(toShare: [], read: healthDataTypes) { [weak self] success, error in
            DispatchQueue.main.async {
                if success {
                    self?.isAuthorized = true
                    self?.fetchAllHealthData()
                } else {
                    self?.errorMessage = error?.localizedDescription ?? "Authorization failed"
                }
            }
        }
    }
    
    func fetchAllHealthData() {
        isLoading = true
        healthMetrics.removeAll()
        
        let group = DispatchGroup()
        
        // Fetch different types of health data
        group.enter()
        fetchHeartRate { group.leave() }
        
        group.enter()
        fetchBloodPressure { group.leave() }
        
        group.enter()
        fetchBloodGlucose { group.leave() }
        
        group.enter()
        fetchBodyTemperature { group.leave() }
        
        group.enter()
        fetchWeight { group.leave() }
        
        group.enter()
        fetchSteps { group.leave() }
        
        group.enter()
        fetchStandHours { group.leave() }
        
        group.enter()
        fetchActiveEnergy { group.leave() }
        
        group.enter()
        fetchWorkouts { group.leave() }
        
        group.enter()
        fetchSleepData { group.leave() }
        
        group.enter()
        fetchFlightsClimbed { group.leave() }
        
        group.notify(queue: .main) {
            self.isLoading = false
            self.healthMetrics.sort { $0.date > $1.date }
        }
    }
    
    private func fetchHeartRate(completion: @escaping () -> Void) {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: heartRateType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
                    let metric = HealthMetric(
                        type: "Heart Rate",
                        value: value,
                        unit: "bpm",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchBloodPressure(completion: @escaping () -> Void) {
        guard let systolicType = HKQuantityType.quantityType(forIdentifier: .bloodPressureSystolic),
              let diastolicType = HKQuantityType.quantityType(forIdentifier: .bloodPressureDiastolic) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        // Fetch systolic readings
        let systolicQuery = HKSampleQuery(sampleType: systolicType,
                                         predicate: predicate,
                                         limit: HKObjectQueryNoLimit,
                                         sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.millimeterOfMercury())
                    let metric = HealthMetric(
                        type: "Blood Pressure",
                        value: value,
                        unit: "mmHg",
                        date: sample.startDate,
                        notes: "Systolic"
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(systolicQuery)
    }
    
    private func fetchBloodGlucose(completion: @escaping () -> Void) {
        guard let bloodGlucoseType = HKQuantityType.quantityType(forIdentifier: .bloodGlucose) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: bloodGlucoseType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.gramUnit(with: .milli).unitDivided(by: .literUnit(with: .deci)))
                    let metric = HealthMetric(
                        type: "Blood Sugar",
                        value: value,
                        unit: "mg/dL",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchBodyTemperature(completion: @escaping () -> Void) {
        guard let temperatureType = HKQuantityType.quantityType(forIdentifier: .bodyTemperature) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: temperatureType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.degreeCelsius())
                    let metric = HealthMetric(
                        type: "Temperature",
                        value: value,
                        unit: "°C",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchWeight(completion: @escaping () -> Void) {
        guard let weightType = HKQuantityType.quantityType(forIdentifier: .bodyMass) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: weightType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.gramUnit(with: .kilo))
                    let metric = HealthMetric(
                        type: "Weight",
                        value: value,
                        unit: "kg",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    func getMetrics(for type: String) -> [HealthMetric] {
        return healthMetrics.filter { $0.type == type }
    }
    
    private func fetchSteps(completion: @escaping () -> Void) {
        guard let stepsType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: stepsType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.count())
                    let metric = HealthMetric(
                        type: "Steps",
                        value: value,
                        unit: "steps",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchStandHours(completion: @escaping () -> Void) {
        guard let standHoursType = HKQuantityType.quantityType(forIdentifier: .appleStandTime) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: standHoursType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.second()) / 3600.0 // Convert seconds to hours
                    let metric = HealthMetric(
                        type: "Stand Hours",
                        value: value,
                        unit: "hours",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchActiveEnergy(completion: @escaping () -> Void) {
        guard let activeEnergyType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: activeEnergyType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.kilocalorie())
                    let metric = HealthMetric(
                        type: "Active Energy",
                        value: value,
                        unit: "kcal",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchFlightsClimbed(completion: @escaping () -> Void) {
        guard let flightsType = HKQuantityType.quantityType(forIdentifier: .flightsClimbed) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: flightsType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKQuantitySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let value = sample.quantity.doubleValue(for: HKUnit.count())
                    let metric = HealthMetric(
                        type: "Flights Climbed",
                        value: value,
                        unit: "flights",
                        date: sample.startDate
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchWorkouts(completion: @escaping () -> Void) {
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: HKObjectType.workoutType(),
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKWorkout], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for workout in samples {
                    let duration = workout.duration / 60.0 // Convert to minutes
                    let activityName = workout.workoutActivityType.name
                    let metric = HealthMetric(
                        type: "Workouts",
                        value: duration,
                        unit: "minutes",
                        date: workout.startDate,
                        notes: activityName
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchSleepData(completion: @escaping () -> Void) {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            completion()
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: Calendar.current.date(byAdding: .day, value: -30, to: Date()),
                                                   end: Date(),
                                                   options: .strictStartDate)
        
        let query = HKSampleQuery(sampleType: sleepType,
                                 predicate: predicate,
                                 limit: HKObjectQueryNoLimit,
                                 sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)]) { [weak self] _, samples, error in
            
            guard let samples = samples as? [HKCategorySample], error == nil else {
                DispatchQueue.main.async { completion() }
                return
            }
            
            DispatchQueue.main.async {
                for sample in samples {
                    let duration = sample.endDate.timeIntervalSince(sample.startDate) / 3600.0 // Convert to hours
                    let sleepStage = self?.getSleepStageName(sample.value) ?? "Sleep"
                    let metric = HealthMetric(
                        type: "Sleep",
                        value: duration,
                        unit: "hours",
                        date: sample.startDate,
                        notes: sleepStage
                    )
                    self?.healthMetrics.append(metric)
                }
                completion()
            }
        }
        
        healthStore.execute(query)
    }
    
    private func getSleepStageName(_ value: Int) -> String {
        switch value {
        case HKCategoryValueSleepAnalysis.asleep.rawValue:
            return "Asleep"
        case HKCategoryValueSleepAnalysis.awake.rawValue:
            return "Awake"
        case HKCategoryValueSleepAnalysis.inBed.rawValue:
            return "In Bed"
        default:
            return "Sleep"
        }
    }
    
    func refreshData() {
        guard isAuthorized else {
            requestAuthorization()
            return
        }
        fetchAllHealthData()
    }
}

// Extension to get workout activity name
extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running: return "Running"
        case .walking: return "Walking"
        case .cycling: return "Cycling"
        case .swimming: return "Swimming"
        case .yoga: return "Yoga"
        case .functionalStrengthTraining: return "Strength Training"
        case .traditionalStrengthTraining: return "Weight Training"
        case .coreTraining: return "Core Training"
        case .flexibility: return "Flexibility"
        case .dance: return "Dance"
        case .basketball: return "Basketball"
        case .tennis: return "Tennis"
        case .golf: return "Golf"
        case .hiking: return "Hiking"
        case .americanFootball: return "Football"
        case .soccer: return "Soccer"
        case .baseball: return "Baseball"
        case .kickboxing: return "Kickboxing"
        case .boxing: return "Boxing"
        case .pilates: return "Pilates"
        case .crossTraining: return "Cross Training"
        case .elliptical: return "Elliptical"
        case .stairClimbing: return "Stair Climbing"
        case .rowing: return "Rowing"
        case .jumpRope: return "Jump Rope"
        default: return "Other Workout"
        }
    }
} 