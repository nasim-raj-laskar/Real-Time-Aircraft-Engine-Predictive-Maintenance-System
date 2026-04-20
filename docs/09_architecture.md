# System Architecture

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Data Sources
        A[CSV Dataset<br/>C-MAPSS]
    end
    
    subgraph Streaming Layer
        B[Kafka Producer<br/>Telemetry Simulator]
        C[Kafka Topic<br/>engine_telemetry]
        D[Feature Consumer<br/>Stream Processor]
    end
    
    subgraph Feature Store
        E[Redis<br/>Online Features]
        F[S3/Parquet<br/>Offline Features]
    end
    
    subgraph ML Pipeline
        G[Training Pipeline<br/>XGBoost/LSTM]
        H[MLflow<br/>Model Registry]
    end
    
    subgraph Inference
        I[FastAPI<br/>Prediction Service]
        J[Model Serving]
    end
    
    subgraph Monitoring
        K[Prometheus<br/>Metrics]
        L[Grafana<br/>Dashboards]
        M[Evidently<br/>Drift Detection]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    D --> F
    F --> G
    G --> H
    H --> J
    E --> I
    J --> I
    I --> K
    K --> L
    E --> M
    M --> L
    
    style A fill:#E8F4F8,stroke:#333,stroke-width:2px,color:#000
    style C fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
    style E fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    style H fill:#87CEEB,stroke:#333,stroke-width:2px,color:#000
    style I fill:#98FB98,stroke:#333,stroke-width:2px,color:#000
    style L fill:#DDA0DD,stroke:#333,stroke-width:2px,color:#000
```

---

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant CSV as CSV Files
    participant KP as Kafka Producer
    participant KT as Kafka Topic
    participant FC as Feature Consumer
    participant R as Redis
    participant S3 as S3/Parquet
    participant API as Inference API
    participant Model as ML Model
    participant Mon as Monitoring
    
    CSV->>KP: Read row by row
    KP->>KT: Publish event (engine_id, cycle, sensors)
    KT->>FC: Consume event
    
    FC->>FC: Compute rolling features
    FC->>R: Write online features
    FC->>S3: Write offline features
    
    Note over API: Client requests prediction
    API->>R: Fetch features for engine_id
    R-->>API: Return feature vector
    API->>Model: predict(features)
    Model-->>API: RUL prediction
    API->>API: Compute failure risk
    API->>Mon: Log metrics
    API-->>API: Return response
    
    Note over S3,Model: Periodic retraining
    S3->>Model: Load historical features
    Model->>Model: Train new version
```

---

## Component Interaction Map

```mermaid
graph TB
    subgraph External
        U[User/Client]
        D[Dataset Files]
    end
    
    subgraph Ingestion
        P[Producer]
        K[Kafka]
    end
    
    subgraph Processing
        C[Consumer]
        FE[Feature Engineering]
    end
    
    subgraph Storage
        R[Redis<br/>Hot Storage]
        S[S3<br/>Cold Storage]
        ML[MLflow<br/>Model Store]
    end
    
    subgraph Compute
        T[Training Job]
        I[Inference API]
    end
    
    subgraph Observability
        PR[Prometheus]
        G[Grafana]
        E[Evidently]
    end
    
    D --> P
    P --> K
    K --> C
    C --> FE
    FE --> R
    FE --> S
    S --> T
    T --> ML
    
    U --> I
    I --> R
    I --> ML
    I --> PR
    PR --> G
    R --> E
    E --> G
    
    style R fill:#FF6B6B,stroke:#333,stroke-width:2px,color:#000
    style S fill:#4169E1,stroke:#333,stroke-width:2px,color:#fff
    style ML fill:#32CD32,stroke:#333,stroke-width:2px,color:#000
    style I fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
```

---

## Deployment Architecture

```mermaid
graph TB
    subgraph Docker Compose / Kubernetes
        subgraph Message Queue
            ZK[Zookeeper]
            KF[Kafka Broker]
        end
        
        subgraph Data Stores
            RD[Redis]
            S3[MinIO/S3]
        end
        
        subgraph ML Services
            MLF[MLflow Server]
            TR[Training Container]
        end
        
        subgraph Stream Processing
            PROD[Producer Container]
            CONS[Consumer Container]
        end
        
        subgraph API Layer
            API1[Inference API - Instance 1]
            API2[Inference API - Instance 2]
            LB[Load Balancer]
        end
        
        subgraph Monitoring Stack
            PROM[Prometheus]
            GRAF[Grafana]
            EVID[Evidently Service]
        end
    end
    
    ZK --> KF
    PROD --> KF
    KF --> CONS
    CONS --> RD
    CONS --> S3
    S3 --> TR
    TR --> MLF
    
    LB --> API1
    LB --> API2
    API1 --> RD
    API2 --> RD
    API1 --> MLF
    API2 --> MLF
    
    API1 --> PROM
    API2 --> PROM
    PROM --> GRAF
    RD --> EVID
    EVID --> GRAF
    
    style KF fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
    style RD fill:#FF6B6B,stroke:#333,stroke-width:2px,color:#000
    style LB fill:#87CEEB,stroke:#333,stroke-width:2px,color:#000
    style GRAF fill:#DDA0DD,stroke:#333,stroke-width:2px,color:#000
```

---

## Feature Store Architecture

```mermaid
flowchart LR
    subgraph Ingestion
        A[Raw Telemetry]
    end
    
    subgraph Feature Engineering
        B[Rolling Stats]
        C[Deviation Features]
        D[Domain Features]
    end
    
    subgraph Online Store - Redis
        E[engine:id:features<br/>Latest vector]
        F[engine:id:buffer<br/>Last 30 cycles]
        G[engine:id:baseline<br/>Healthy state]
    end
    
    subgraph Offline Store - S3
        H[Parquet Files<br/>Historical features]
        I[Partitioned by date]
    end
    
    subgraph Consumers
        J[Inference API<br/>Low latency reads]
        K[Training Pipeline<br/>Batch reads]
    end
    
    A --> B
    A --> C
    A --> D
    
    B --> E
    C --> E
    D --> E
    
    B --> F
    C --> G
    
    E --> H
    F --> H
    G --> H
    H --> I
    
    E --> J
    F --> J
    G --> J
    I --> K
    
    style E fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    style H fill:#87CEEB,stroke:#333,stroke-width:2px,color:#000
    style J fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
```

---

## Model Training Pipeline

```mermaid
flowchart TD
    A[Offline Feature Store<br/>S3/Parquet] --> B[Load Historical Data]
    B --> C[Train/Val Split<br/>by Engine ID]
    
    C --> D[XGBoost Training]
    C --> E[LSTM Training]
    
    D --> F[Hyperparameter Tuning<br/>Optuna]
    E --> F
    
    F --> G[Model Evaluation<br/>RMSE + NASA Score]
    
    G --> H{RMSE < Threshold?}
    H -->|No| I[Log to MLflow<br/>Experiment]
    I --> F
    
    H -->|Yes| J[Register Model<br/>MLflow Registry]
    J --> K[Staging Environment]
    K --> L[A/B Test vs Production]
    
    L --> M{Better Performance?}
    M -->|Yes| N[Promote to Production]
    M -->|No| O[Keep Current Model]
    
    N --> P[Update Inference Service]
    
    style G fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
    style H fill:#FFA500,stroke:#333,stroke-width:2px,color:#000
    style N fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    style O fill:#FF6B6B,stroke:#333,stroke-width:2px,color:#000
```

---

## Real-Time Inference Flow

```mermaid
flowchart TD
    A[New Cycle Event<br/>Kafka] --> B[Feature Consumer]
    
    B --> C[Fetch Rolling Buffer<br/>Redis]
    C --> D[Compute Features]
    D --> E[Write to Redis<br/>engine:id:features]
    
    F[Client Request<br/>POST /predict] --> G[Inference API]
    G --> H[Read Features<br/>from Redis]
    
    H --> I{Features Found?}
    I -->|No| J[Return 404]
    I -->|Yes| K[Load Model<br/>from Memory]
    
    K --> L[Model.predict]
    L --> M[RUL Prediction]
    M --> N[Compute Risk Score<br/>risk = 1 - RUL/125]
    
    N --> O{Risk Level?}
    O -->|< 0.3| P[LOW]
    O -->|0.3-0.6| Q[MEDIUM]
    O -->|0.6-0.8| R[HIGH]
    O -->|> 0.8| S[CRITICAL]
    
    S --> T[Trigger Alert]
    
    P --> U[Return Response]
    Q --> U
    R --> U
    S --> U
    
    U --> V[Log Metrics<br/>Prometheus]
    
    style E fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    style L fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
    style S fill:#FF6B6B,stroke:#333,stroke-width:2px,color:#000
    style T fill:#FF6B6B,stroke:#333,stroke-width:2px,color:#000
```

---

## Monitoring Architecture

```mermaid
flowchart TB
    subgraph Data Sources
        A[Inference API]
        B[Feature Consumer]
        C[Redis]
        D[Kafka]
    end
    
    subgraph Metrics Collection
        E[Prometheus<br/>Scraper]
    end
    
    subgraph Metrics Storage
        F[Prometheus TSDB]
    end
    
    subgraph Visualization
        G[Grafana Dashboards]
    end
    
    subgraph ML Monitoring
        H[Evidently<br/>Drift Detection]
    end
    
    subgraph Alerting
        I[Alert Manager]
        J[PagerDuty/Slack]
    end
    
    A -->|/metrics endpoint| E
    B -->|/metrics endpoint| E
    C -->|Redis Exporter| E
    D -->|Kafka Exporter| E
    
    E --> F
    F --> G
    
    C --> H
    H --> G
    
    F --> I
    I --> J
    
    style E fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
    style G fill:#DDA0DD,stroke:#333,stroke-width:2px,color:#000
    style H fill:#87CEEB,stroke:#333,stroke-width:2px,color:#000
    style J fill:#FF6B6B,stroke:#333,stroke-width:2px,color:#000
```
