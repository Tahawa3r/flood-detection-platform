# Projet de Fin d'Année (PFA) - EMSI IIR
## Section : Résumé et Introduction

---

### 1. Informations Générales
- **Titre du projet** : Plateforme de Détection et d'Évaluation des Risques d'Inondation par Imagerie Satellitaire Radar et Intelligence Artificielle
- **Option** : Informatique et Ingénierie des Réseaux (IIR) - Option Intelligence Artificielle
- **Étudiant 1** : Taha Azzouzi
- **Étudiant 2** : [Nom Prénom]
- **Numéro de groupe** : [Groupe]
- **Encadrant pédagogique EMSI** : [Pr. Nom]
- **Année académique** : 2025 / 2026
- **Date de soutenance** : [Date]

---

### 2. Résumé (French)
Ce projet présente le développement d'une plateforme intégrée dédiée à la détection et à l'évaluation automatisée des risques d'inondation. En s'appuyant sur l'imagerie satellitaire radar Sentinel-1 (SAR) et des algorithmes d'apprentissage profond, la solution permet une surveillance continue, même en présence d'une couverture nuageuse dense. L'architecture repose sur un backend robuste développé avec **FastAPI**, orchestrant la récupération des données via **Google Earth Engine** et le traitement par un modèle de segmentation sémantique **U-Net**. Un frontend interactif en **React** offre aux utilisateurs une interface cartographique permettant de délimiter des zones d'intérêt et de visualiser l'étendue des crues en temps réel. Les résultats obtenus démontrent une haute précision dans l'identification des zones sinistrées, offrant ainsi un outil d'aide à la décision précieux pour la gestion des catastrophes naturelles au Maroc et ailleurs.

**Mots-clés** : Inondation, Sentinel-1, SAR, Deep Learning, U-Net, FastAPI, SIG, Gestion de crise.

---

### 3. Abstract (English)
This project focuses on the development of an integrated platform for the automated detection and assessment of flood risks. Leveraging Sentinel-1 Synthetic Aperture Radar (SAR) satellite imagery and deep learning algorithms, the solution enables continuous monitoring regardless of cloud cover. The architecture features a robust **FastAPI** backend that orchestrates data acquisition through **Google Earth Engine** and processing via a **U-Net** semantic segmentation model. An interactive **React** frontend provides users with a mapping interface to define regions of interest and visualize flood extent in real-time. The results demonstrate high accuracy in identifying disaster areas, providing a valuable decision-support tool for natural disaster management in Morocco and beyond.

**Keywords**: Flood Detection, Sentinel-1, SAR, Deep Learning, U-Net, FastAPI, GIS, Disaster Management.

---

### 4. Introduction
#### 4.1. Contexte et Problématique
Le changement climatique a intensifié la fréquence des phénomènes météorologiques extrêmes, plaçant les inondations parmi les catastrophes naturelles les plus dévastatrices au monde. Au Maroc, plusieurs régions sont régulièrement confrontées à des crues soudaines qui causent des dommages matériels et humains considérables. La rapidité d'intervention et la précision de l'évaluation des zones touchées sont des facteurs critiques pour les autorités de protection civile.

Cependant, les méthodes traditionnelles de surveillance se heurtent à plusieurs obstacles :
1. **Limites de l'optique** : Les satellites classiques ne peuvent pas "voir" à travers les nuages, souvent présents lors des tempêtes.
2. **Contraintes logistiques** : Les relevés de terrain sont dangereux et lents lors d'une crise.
3. **Volume de données** : Le traitement manuel de l'imagerie satellitaire à grande échelle est chronophage.

#### 4.2. Solution proposée
Pour répondre à ces défis, ce projet propose une **Plateforme de Détection et d'Évaluation des Risques d'Inondation**. L'originalité de la solution réside dans l'utilisation de l'imagerie radar (SAR) qui traverse les nuages et l'automatisation complète du pipeline d'analyse par l'Intelligence Artificielle.

#### 4.3. Objectifs du projet
Les principaux objectifs visés par cette plateforme sont :
- **Automatisation** : Récupérer et traiter les données satellitaires sans intervention humaine complexe.
- **Précision** : Utiliser des modèles U-Net pour une segmentation fine des zones inondées.
- **Accessibilité** : Fournir une interface web intuitive pour les décideurs non-spécialistes en télédétection.
- **Réactivité** : Réduire le temps entre l'acquisition de l'image et la production de la carte de risque.

#### 4.4. Structure du rapport
Le présent rapport est structuré en quatre chapitres :
- **Chapitre 1 : Contexte général et étude de l'existant**, où nous analysons l'état de l'art et les technologies SAR.
- **Chapitre 2 : Analyse et spécification des besoins**, détaillant les exigences fonctionnelles et techniques.
- **Chapitre 3 : Conception de la solution**, présentant l'architecture globale et les modèles de données.
- **Chapitre 4 : Réalisation et tests**, exposant l'implémentation logicielle et les résultats expérimentaux.
