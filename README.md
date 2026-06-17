# Complete Football Analytics

Welcome to the **Complete Football Analytics** repository! This project is a comprehensive resource for learning and applying data science, machine learning, and automated data engineering techniques to football (soccer) data. It covers everything from Python basics to advanced web scraping, data visualization, predictive modeling, and production-ready automated reporting pipelines.

---

## 📂 Repository Structure

The repository is organized into progressive modules and production subprojects:

### 📚 Modules

*   **Module 1: Python Fundamentals**
    *   Learn the core building blocks of Python programming.
    *   Covers: Syntax, Variables, Data Types, Control Flows (If/Else, Loops), Functions, and Error Handling.

*   **Module 3: Data Acquisition & Web Scraping**
    *   Master gathering football data from various web sources and APIs.
    *   **APIs & Libraries**: `Statsbombpy`, `Soccerdata`.
    *   **Scraping Targets**: FBRef, Sofascore, Understat, Fotmob, WhoScored.
    *   **Techniques**: Handling requests, parsing HTML with `BeautifulSoup`, and using browser automation tools like `Playwright` and `Undetected Chromedriver`.

*   **Module 4: Data Visualization**
    *   Create professional-grade football visualizations.
    *   **Libraries**: `Matplotlib`, `Seaborn`, and `mplsoccer`.
    *   **Visualizations**: Scatter Plots, Heatmaps, Radar Charts, Pizza Plots (Percentile Ranks), Pass Networks, Shotmaps, and xG Flow Charts.

*   **Module 5: Data Analysis**
    *   Dive deep into data manipulation and statistical analysis.
    *   **Tools**: `Pandas` and `Numpy`.
    *   **Topics**: Data Cleaning, Basic Statistics, Correlation Analysis.

*   **Module 6: Machine Learning for Football**
    *   Apply ML algorithms to football data.
    *   **Applications**: Match outcome predictions (Classification), player valuation/xG models (Regression), and player/team profile clustering (Unsupervised).

---

## 🏆 Subprojects

*   **Barcelona Elite Analytics**
    *   A web-based dashboard and API for analyzing Barcelona matches, passing networks, final third entries, and shot maps.
    *   See [barcelona/README.md](file:///c:/Users/puzik/BCNFINAL/barcelona/README.md) (or equivalent/workspace files) for details.


## 🛠️ Installation & Setup

Ensure you have Python 3.10+ installed. It is recommended to use a virtual environment.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/RShiri/BCNFINAL.git
    cd BCNFINAL
    ```

2.  **Install Core Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables**:
    *   Set up your `.env` configuration file with appropriate credentials in the root directory (based on `.env.template`).

---

## 📈 Usage

Most tutorial content is provided in **Jupyter Notebooks (`.ipynb`)**. To explore:

1.  Launch Jupyter:
    ```bash
    jupyter notebook
    ```
2.  Open the desired notebook (e.g., `3.2 Statsbomb API.ipynb`) and execute the cells.

For running the Barcelona pipeline scripts, see the instructions in the `barcelona/` folder.

---

## 🤝 Contributing

Feel free to fork this repository, submit Pull Requests, or open Issues if you have suggestions for new football data visualization templates or analytics models!