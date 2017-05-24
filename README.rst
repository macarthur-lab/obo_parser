Parses ontologies in .obo format (such as the Human Phenotype Ontology) and converts them to a .tsv table.

.. image:: https://travis-ci.org/macarthur-lab/obo_parser.svg?branch=master
    :target: https://travis-ci.org/macarthur-lab/obo_parser
    
    
**Install**  

.. code:: bash

  git clone https://github.com/macarthur-lab/obo_parser.git  

**Test**  

.. code:: bash

  python -m unittest discover

**Run**  

Examples:  

.. code:: bash

  python obo_parser.py --help  
  python obo_parser.py -r HP:0000118 http://purl.obolibrary.org/obo/hp.obo -o hpo.tsv  
  python obo_parser.py -c -r HP:0000118 http://purl.obolibrary.org/obo/hp.obo | cut -f 1,2,4,5,10,11 > hp.tsv  
