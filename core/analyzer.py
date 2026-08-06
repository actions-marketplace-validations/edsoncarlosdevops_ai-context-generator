from dataclasses import dataclass
from typing import List, Optional
from core.scanner import ScanResult

@dataclass
class ProjectProfile:
    primary_language: str
    secondary_languages: List[str]
    frameworks: List[str]
    infra_tools: List[str]
    cicd_platforms: List[str]
    architecture_hints: List[str]
    domain: str
    security_risk_level: str
    existing_agents_md: Optional[str]
    has_tests: bool
    test_commands: List[str]
    build_commands: List[str]

class ProjectAnalyzer:
    def analyze(self, scan_result: ScanResult) -> ProjectProfile:
        sorted_langs = sorted(scan_result.language_counts.items(), key=lambda x: x[1], reverse=True)
        primary_lang = sorted_langs[0][0] if sorted_langs else "Unknown"
        secondary_langs = [l[0] for l in sorted_langs[1:]]

        framework_map = {
            'fastapi': 'FastAPI', 'ros2': 'ROS 2', 'terraform': 'Terraform',
            'next': 'Next.js', 'react': 'React', 'django': 'Django',
            'flask': 'Flask', 'express': 'Express', 'spring': 'Spring Boot',
            'rails': 'Ruby on Rails', 'vue': 'Vue.js', 'angular': 'Angular'
        }
        frameworks = []
        deps_lower = [d.lower() for d in scan_result.dependencies]
        for k, v in framework_map.items():
            if any(k in d for d in deps_lower):
                frameworks.append(v)
        frameworks = list(set(frameworks))

        infra_tools = []
        for infra in scan_result.infra_files:
            if 'Docker' in infra or 'docker' in infra: infra_tools.append('Docker')
            if 'k8s' in infra or 'helm' in infra: infra_tools.append('Kubernetes')
            if '.tf' in infra: infra_tools.append('Terraform')
        infra_tools = list(set(infra_tools))

        cicd_platforms = []
        for cicd in scan_result.cicd_files:
            if 'github' in cicd.lower(): cicd_platforms.append('GitHub Actions')
            elif 'gitlab' in cicd.lower(): cicd_platforms.append('GitLab CI')
            elif 'azure' in cicd.lower(): cicd_platforms.append('Azure DevOps')
            elif 'jenkins' in cicd.lower(): cicd_platforms.append('Jenkins')
        cicd_platforms = list(set(cicd_platforms))

        arch_hints = []
        if 'microservices' in str(scan_result.infra_files): arch_hints.append('microservices')
        if any('api' in d for d in scan_result.dependencies): arch_hints.append('api')

        domain = 'general'
        if 'ROS 2' in frameworks or 'ros2' in deps_lower: domain = 'robotics'
        elif 'stripe' in deps_lower or 'plaid' in deps_lower: domain = 'fintech'
        elif 'react' in frameworks or 'django' in frameworks: domain = 'web'
        elif 'pandas' in deps_lower or 'airflow' in deps_lower: domain = 'data-engineering'
        elif 'Docker' in infra_tools and 'Terraform' in infra_tools: domain = 'devops'

        security_risk_level = 'low'
        if domain in ['fintech', 'robotics', 'devops'] or any(dep in deps_lower for dep in ['jwt', 'oauth', 'stripe']):
            security_risk_level = 'high'
        elif len(scan_result.dependencies) > 50:
            security_risk_level = 'medium'

        return ProjectProfile(
            primary_language=primary_lang,
            secondary_languages=secondary_langs,
            frameworks=frameworks,
            infra_tools=infra_tools,
            cicd_platforms=cicd_platforms,
            architecture_hints=arch_hints,
            domain=domain,
            security_risk_level=security_risk_level,
            existing_agents_md=scan_result.existing_agents_md,
            has_tests=scan_result.has_tests,
            test_commands=scan_result.test_commands,
            build_commands=scan_result.build_commands
        )
