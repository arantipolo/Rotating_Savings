## Contributing to Rotating Savings

Thank you for your interest in helping improve the Rotating Savings web application!  
Whether you want to add new features, fix bugs, or improve the UI, this guide will help you get started.

---

### Development Setup

#### Clone the repository to your computer:

```bash
git clone <repo link>
cd Rotating_Savings
```

#### Create a Python virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```
#### Install Python dependencies:
```bash
pip install -r requirements.txt
```

#### Run the development server:
```bash
python run.py
```

#### Branching & Workflow

To keep the main branch clean (protected), always use feature branches:

```bash
git checkout -b feature/<your-feature-name>
```

#### Open a Pull Request on GitHub:
 - Base branch = main.

 - Compare branch = your feature branch.

 - Submit pull request and request review if needed.
 - Merge pull request after approval.

#### Testing
 - Test changes locally before creating a pull request.
 - Make sure nothing breaks the existing feature.