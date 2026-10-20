"""Evidence gates. No model response can bypass these rules."""
import math

VERSION = '1.0'
CHOICES = ('CONTINUE', 'MODIFIE', 'PIVOTE', 'ABANDONNE', 'SCALE')

def decide(m):
    for key in ('tests', 'visitors', 'conversions', 'repeatable_runs', 'minutes', 'budget_minutes'):
        value = m.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid metric: ' + key)
    if m.get('conversions', 0) > m.get('visitors', 0):
        raise ValueError('Conversions exceed visitors')
    def result(choice, why, next_step):
        return dict(choice=choice, reason=why, next_action=next_step, policy=VERSION,
                    external_execution=False, metrics=m)
    if not m.get('technical_pass', False):
        return result('MODIFIE', 'La validation technique échoue ; aucune conclusion sur le marché.', 'Corriger le défaut et relancer les tests bornés.')
    if m.get('budget_minutes', 0) and m.get('minutes', 0) >= m['budget_minutes']:
        return result('MODIFIE', 'Budget de temps atteint : pause de la boucle, sans condamner l’idée.', 'Revue humaine avant un nouveau budget.')
    if m.get('source') != 'real':
        return result('CONTINUE', 'Données fictives ou techniques : marché non validé, abandon et scale interdits.', 'Préparer un protocole de validation réelle, sous approbation.')
    if m.get('tests', 0) < 3 or m.get('visitors', 0) < 300:
        return result('CONTINUE', 'Échantillon insuffisant pour abandonner ou développer.', 'Améliorer la distribution ; trois tests et 300 visites qualifiées minimum.')
    rate = m.get('conversions', 0) / max(m.get('visitors', 0), 1)
    if rate >= .05 and m.get('repeatable_runs', 0) >= 3 and m.get('unit_economics_positive') is True:
        return result('SCALE', 'Conversion ≥ 5 %, trois résultats reproductibles et économie unitaire positive.', 'Préparer un plan de croissance ; toute exécution externe reste interdite.')
    if rate < .01 and m.get('problem_confirmed') is True:
        return result('PIVOTE', 'Problème confirmé mais solution peu adoptée après plusieurs tests.', 'Changer la solution et tester une seule nouvelle hypothèse.')
    if rate < .01 and m.get('distinct_hypotheses', 0) >= 3 and m.get('negative_feedback_confirmed') is True:
        return result('ABANDONNE', 'Trois hypothèses testées et retours négatifs concordants ; signal faible.', 'Archiver les leçons, préserver le projet et explorer une autre hypothèse.')
    return result('MODIFIE', 'Données suffisantes mais pas de signal reproductible de croissance.', 'Changer offre, prix ou parcours ; fixer un budget avant le prochain test.')
