def phetk_icd_query(ds):
    """
    This method is optimized for the All of Us platform.

    It includes 3 queries: icd_query, v_icd_vocab_query, and final_query.
    icd_query retrieves all ICD codes from the OMOP database.
    v_icd_vocab_query gets the ICD codes starting with "V" from icd_query and check vocabulary_id using concept_id.
    final_query union distinct icd_query without V codes
    and v_icd_vocab_query which has V codes with proper vocabulary_ids.

    The reason for this is to ensure vocabulary_id values of V codes, many of which overlap between ICD9CM & ICD10CM,
    are correct.

    :param ds: Google BigQuery dataset ID containing OMOP data tables
    :return: a SQL query that would generate a table contains participant IDs and their ICD codes from unique dates
    """
    icd_query: str = f"""
        (
            SELECT DISTINCT
                co.person_id,
                co.condition_start_date AS date,
                c.vocabulary_id AS vocabulary_id,
                c.concept_code AS ICD,
                co.condition_concept_id AS concept_id
            FROM
                {ds}.condition_occurrence AS co
            INNER JOIN
                {ds}.concept AS c
            ON
                co.condition_source_value = c.concept_code
            WHERE
                c.vocabulary_id in ("ICD9CM", "ICD10CM")
        )
        UNION DISTINCT
        (
            SELECT DISTINCT
                co.person_id,
                co.condition_start_date AS date,
                c.vocabulary_id AS vocabulary_id,
                c.concept_code AS ICD,
                co.condition_concept_id AS concept_id
            FROM
                {ds}.condition_occurrence AS co
            INNER JOIN
                {ds}.concept AS c
            ON
                co.condition_source_concept_id = c.concept_id
            WHERE
                c.vocabulary_id in ("ICD9CM", "ICD10CM")
        )
        UNION DISTINCT
        (
            SELECT DISTINCT
                o.person_id,
                o.observation_date AS date,
                c.vocabulary_id AS vocabulary_id,
                c.concept_code AS ICD,
                o.observation_concept_id AS concept_id
            FROM
                {ds}.observation AS o
            INNER JOIN
                {ds}.concept as c
            ON
                o.observation_source_value = c.concept_code
            WHERE
                c.vocabulary_id in ("ICD9CM", "ICD10CM")
        )
        UNION DISTINCT
        (
            SELECT DISTINCT
                o.person_id,
                o.observation_date AS date,
                c.vocabulary_id AS vocabulary_id,
                c.concept_code AS ICD,
                o.observation_concept_id AS concept_id
            FROM
                {ds}.observation AS o
            INNER JOIN
                {ds}.concept as c
            ON
                o.observation_source_concept_id = c.concept_id
            WHERE
                c.vocabulary_id in ("ICD9CM", "ICD10CM")
        )
    """

    v_icd_vocab_query: str = f"""
        SELECT DISTINCT
            v_icds.person_id,
            v_icds.date,
            v_icds.ICD,
            c.vocabulary_id
        FROM
            (
                SELECT
                    *
                FROM
                    ({icd_query}) AS icd_events
                WHERE
                    icd_events.ICD LIKE "V%"
            ) AS v_icds
        INNER JOIN
            {ds}.concept_relationship AS cr
        ON
            v_icds.concept_id = cr.concept_id_1
        INNER JOIN
            {ds}.concept AS c
        ON
            cr.concept_id_2 = c.concept_id
        WHERE
            c.vocabulary_id IN ("ICD9CM", "ICD10CM")
        AND
            v_icds.ICD = c.concept_code
        AND NOT
            v_icds.vocabulary_id != c.vocabulary_id
    """

    final_query: str = f"""
        (
            SELECT DISTINCT
                person_id,
                date,
                ICD,
                vocabulary_id
            FROM 
                ({icd_query})
            WHERE
                NOT ICD LIKE "V%"
        )
        UNION DISTINCT
        (
            SELECT DISTINCT
                *
            FROM
                ({v_icd_vocab_query})
        )
    """

    return final_query