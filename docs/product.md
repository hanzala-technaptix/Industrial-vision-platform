Yes. I checked specifically for **real industrial/manufacturing datasets that we can use to build the POC before your CEO obtains proprietary factory data**.

The important conclusion is:

> **Yes, there is enough public data to build a credible Factory AI POC — but there is no single public dataset that covers the whole product.**
>
> We should combine several datasets, and clearly distinguish **public benchmark data** from **synthetic demo data** and later **customer data**.

## 1. For machine downtime / production timing — YES

This is actually the easiest part to start with.

I found a manufacturing downtime dataset containing **production-batch records, start/end timestamps, downtime reasons, operator information and product information** for a bottling line. ([Kaggle][1])

[Manufacturing Efficiency in Downtime Operations dataset](https://www.kaggle.com/datasets/agungpambudi/predict-manufacturing-downtime-performance-dataset?utm_source=chatgpt.com)

This is useful for building your:

**Machine/Production Operations module**

For example:

```text
Production Batch
        ↓
Start Time
End Time
Downtime
Downtime Reason
Operator
Product
        ↓
Factory Analytics
```

We can calculate:

* Total production time
* Downtime
* Runtime
* Downtime %
* Production efficiency
* Production per hour
* Downtime reasons
* Operator/batch performance
* Shift-level performance

### But there is an important limitation

This dataset is **not camera data**.

So we cannot say:

> "Our computer vision detected this machine downtime."

Instead we can use it to build and validate the **operations analytics layer**.

Then later:

```text
REAL CAMERA
     ↓
AI detects machine state
     ↓
Machine events
     ↓
Same database
     ↓
Same dashboard
```

The analytics platform doesn't need to change.

---

# 2. For machine condition / anomaly — YES

There is a very good public dataset called **MIMII** from Hitachi.

It contains recordings from industrial:

* valves
* pumps
* fans
* slide rails

with both **normal and anomalous machine sounds**. The dataset also includes different types of machine abnormalities such as contamination, leakage, imbalance and rail damage. ([Zenodo][2])

[MIMII Dataset](https://zenodo.org/records/3384388?utm_source=chatgpt.com)

This gives us another possible POC module:

**Machine Anomaly Detection**

```text
Machine Sound
      ↓
Audio AI
      ↓
Normal / Anomaly
      ↓
Machine Event
      ↓
Alert
```

So eventually your factory platform isn't only:

> "Camera sees machine stopped."

It can become:

> "Machine is running, but its acoustic signature is abnormal."

That's a much stronger industrial story.

---

# 3. For quality inspection / defects — YES

This is where **MVTec** becomes very useful.

The official MVTec AD dataset contains **5,000+ high-resolution industrial inspection images**, covering 15 object/texture categories, with defect-free and defective samples and pixel-level anomaly annotations. ([MVTec Software][3])

[MVTec AD — Official Dataset](https://www.mvtec.com/research-teaching/datasets/mvtec-ad?utm_source=chatgpt.com)

There is also **MVTec AD 2**, which has **8,000+ high-resolution images** across eight more challenging industrial anomaly scenarios. ([MVTec Software][4])

And **MVTec LOCO AD** is particularly interesting for our use case because it includes **logical manufacturing anomalies**, such as a required component being missing or an object being in an invalid position, in addition to scratches/dents/contamination. ([MVTec Software][5])

### This can power:

```text
Product
   ↓
Vision Inspection
   ↓
Normal / Defective
   ↓
Defect Type
   ↓
Pass / Reject
   ↓
Quality Dashboard
```

So your demo can actually show **real industrial inspection images**, rather than fabricated defect examples.

### Important commercial caveat

The official MVTec AD and AD 2 pages state that these datasets are released under **CC BY-NC-SA 4.0** and are **not permitted for commercial use** without addressing the licensing issue. ([MVTec Software][3])

So I would use them for **internal R&D / technical POC validation**, not assume they're okay for a commercial customer deployment.

---

# 4. For manufacturing process data — YES

Another useful dataset is **SECOM** from the UCI Machine Learning Repository.

It comes from a real semiconductor manufacturing process and contains:

* **1,567 examples**
* **591 features**
* sensor/process measurements
* timestamps
* pass/fail manufacturing labels

The dataset was specifically collected around monitoring signals from a semiconductor manufacturing process and investigating factors associated with yield excursions. ([UCI Machine Learning Repository][6])

[UCI SECOM Manufacturing Dataset](https://archive.ics.uci.edu/dataset/179/secom?utm_source=chatgpt.com)

This could support a future:

**Process / Yield Intelligence module**

```text
Process Measurements
        ↓
AI Analysis
        ↓
Anomaly / Failure Risk
        ↓
Yield Analysis
```

---

# So we can build the POC from multiple sources

This is the architecture I would recommend now:

```text
                 FACTORY AI POC
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
  DOWNTIME DATA   QUALITY DATA     MACHINE DATA
       │               │                │
   Kaggle          MVTec AD          MIMII
       │               │                │
       └───────────────┼────────────────┘
                       │
                       ▼
                UNIFIED DATA MODEL
                       │
                       ▼
                 FACTORY ENGINE
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      TIMELINE     ANALYTICS      ALERTS
          │            │            │
          └────────────┼────────────┘
                       ▼
                   DASHBOARD
```

Then later:

```text
             CEO GETS INDUSTRY CONTACT
                       ↓
              COMPANY PROVIDES DATA
                       ↓
       ┌───────────────┼──────────────┐
       │               │              │
   Camera Video     Log Sheets     PLC / MES
       │               │              │
       └───────────────┼──────────────┘
                       ↓
                 CUSTOMER POC
                       ↓
              CUSTOMER-SPECIFIC AI
```

---

# But there's one thing I would NOT fake

I would **not create fake manual-vs-AI numbers and present them as evidence**.

Instead, our dashboard should explicitly identify the data source.

For example:

### Demo Dashboard

**Data Sources**

🟢 **Public Manufacturing Dataset**
Production/downtime analytics

🟢 **Public Industrial Vision Dataset**
Quality inspection

🟢 **Public Machine Audio Dataset**
Machine anomaly

🟡 **Simulated Factory Events**
Used only where public data doesn't exist

🔵 **Customer Data**
To be connected during customer POC

This makes the demo technically honest.

---

# And this gives your CEO a very good story

Your CEO can demonstrate the platform and say:

> **"This is our generic Factory AI platform. We have demonstrated it using public industrial datasets. We now want to connect it to your actual factory data to measure the same KPIs against your real operations."**

Then ask the company for:

### Minimum data request

**1. Machine/production logs**

```text
Machine ID
Date
Start Time
Stop Time
Downtime
Downtime Reason
Production Quantity
Shift
```

**2. Camera footage**

Even **30–60 minutes of representative footage** can be useful for an initial CV feasibility test.

**3. Quality data**

```text
Product
Good Quantity
Rejected Quantity
Defect Type
Timestamp
```

**4. Optional PLC/MES/SCADA data**

```text
Machine State
Speed
Temperature
Output
Alarm
Runtime
```

And **this is where our "Manual vs AI" idea becomes genuinely powerful**.

We can take:

```text
            COMPANY DATA
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Manual Log         Camera AI
        │                 │
        └────────┬────────┘
                 ▼
           RECONCILIATION
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
   AGREEMENT           DISCREPANCY
       │                   │
       ▼                   ▼
   Accurate            Investigation
```

That's the actual product value.

### My recommendation

**Don't wait for your CEO to get factory data before starting.**

Build the **generic platform now using public datasets**, but design the data model so that **customer data can replace those sources without changing the product architecture**.

Then when your CEO gets access to a real factory, we don't start development from zero—we simply plug in **their video + logs + machine data** and run a real-world validation.

And I think **machine downtime + production timing + manual-vs-observed reconciliation should be one of the headline features**, because it directly attacks a real manual factory process rather than being just another computer-vision demo.

[1]: https://www.kaggle.com/datasets/agungpambudi/predict-manufacturing-downtime-performance-dataset?utm_source=chatgpt.com "Manufacturing Efficiency in Downtime Operations"
[2]: https://zenodo.org/records/3384388?utm_source=chatgpt.com "MIMII Dataset: Sound Dataset for Malfunctioning Industrial Machine Investigation and Inspection | Zenodo"
[3]: https://www.mvtec.com/research-teaching/datasets/mvtec-ad?utm_source=chatgpt.com "MVTec AD | Industrial Anomaly Detection Dataset"
[4]: https://www.mvtec.com/research-teaching/datasets/mvtec-ad-2?utm_source=chatgpt.com "MVTec AD 2 | Advanced Industrial Anomaly Detection Dataset"
[5]: https://www.mvtec.com/research-teaching/datasets/mvtec-loco-ad?utm_source=chatgpt.com "MVTec LOCO AD | Logical Anomaly Detection Dataset"
[6]: https://archive.ics.uci.edu/dataset/179/secom?utm_source=chatgpt.com "UCI Machine Learning Repository"