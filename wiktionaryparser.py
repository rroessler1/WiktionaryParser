import re, requests
from utils import WordData, Definition, RelatedWord
from bs4 import BeautifulSoup
from itertools import zip_longest
from string import digits


LANGUAGES = {
    'en': {
        'ETYMOLOGIES_HEADER': ["etymology"],
        'PRONUNCIATION_HEADER': ["pronunciation"],
        'PARTS_OF_SPEECH': [
            "noun", "verb", "adjective", "adverb", "determiner",
            "article", "preposition", "conjunction", "proper noun",
            "letter", "character", "phrase", "proverb", "idiom",
            "symbol", "syllable", "numeral", "initialism", "interjection",
            "definitions", "pronoun",
        ],
        'RELATIONS': [
            "synonyms", "antonyms", "hypernyms", "hyponyms",
            "meronyms", "holonyms", "troponyms", "related terms",
            "coordinate terms",
        ]
    },

    'es': {
        'PARTS_OF_SPEECH': [
            "sustantivo", "verbo",
            "preposición", "pronombre", "adverbio", "adjetivo", "interjección",
            "conjunción", "onomatopeya",
            "artículo", "contracción"
        ]
    },

    'fr': {
        'PARTS_OF_SPEECH': [
            "nom commun", "verbe", "adjectif", "adverbe", "déterminant",
            "article", "preposition", "conjonction", "nom propre",
            "lettre", "caractère", "expression", "proverbe", "idiome",
            "symbole", "syllabe", "nombre", "acronyme", "interjection",
            "définitions", "pronom", "particule", "prédicat", "participe",
            "suffixe", "locution nominale", "préposition", "forme d’adjectif"
        ]
    },

    'de': {
        'PARTS_OF_SPEECH': [
            "verb", "adjektiv", "substantiv", "artikel", "pronomen", "adverb",
            "interjektion", "konjunktion", "präposition", "kontraktion", "subjunktion",
            "indefinitpronomen", "temporaladverb", "numerale", "demonstrativpronomen"
        ]
    }
}

class WiktionaryParser(object):
    def __init__(self):
        self.url = "https://en.wiktionary.org/wiki/{}?printable=yes"
        self.soup = None
        self.session = requests.Session()
        self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries = 2))
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries = 2))
        self.language = 'english'
        self.language_code = 'en'
        self.current_word = None

    # TODO: the next four methods should be unified into "include_item" and "exclude_item" methods
    #       Store them in class variables and then use them in the "get_included_items" method
    def include_part_of_speech(self, part_of_speech):
        part_of_speech = part_of_speech.lower()
        if part_of_speech not in self.PARTS_OF_SPEECH:
            self.PARTS_OF_SPEECH.append(part_of_speech)
            self.INCLUDED_ITEMS.append(part_of_speech)

    def exclude_part_of_speech(self, part_of_speech):
        part_of_speech = part_of_speech.lower()
        self.PARTS_OF_SPEECH.remove(part_of_speech)
        self.INCLUDED_ITEMS.remove(part_of_speech)

    def include_relation(self, relation):
        relation = relation.lower()
        if relation not in self.RELATIONS:
            self.RELATIONS.append(relation)
            self.INCLUDED_ITEMS.append(relation)

    def exclude_relation(self, relation):
        relation = relation.lower()
        self.RELATIONS.remove(relation)
        self.INCLUDED_ITEMS.remove(relation)

    def get_included_items(self):
        return LANGUAGES.get(self.language_code).get('RELATIONS', []) + \
               LANGUAGES.get(self.language_code).get('PARTS_OF_SPEECH', []) + \
               LANGUAGES.get(self.language_code).get('ETYMOLOGIES_HEADER', []) + \
               LANGUAGES.get(self.language_code).get('PRONUNCIATION_HEADER', [])

    def set_default_language(self, language=None):
        if language is not None:
            self.language = language.lower()

    def get_default_language(self):
        return self.language

    def set_source_language(self, language_code):
        self.language_code = language_code
        self.url = "https://{}.wiktionary.org/wiki/{{}}?printable=yes".format(language_code)

    def clean_html(self):
        unwanted_classes = ['sister-wikipedia', 'thumb', 'reference', 'cited-source']
        for tag in self.soup.find_all(True, {'class': unwanted_classes}):
            tag.extract()

    def remove_digits(self, string):
        return string.translate(str.maketrans('', '', digits)).strip()

    def get_first_word(self, string):
        if ' ' in string:
            string = string[:string.find(' ')]
        if '\xa0' in string:
            string = string[:string.find('\xa0')]
        return string

    def count_digits(self, string):
        return len(list(filter(str.isdigit, string)))

    def get_id_list(self, id_list, content_type):
        if content_type == 'etymologies':
            checklist = LANGUAGES.get(self.language_code).get('ETYMOLOGIES_HEADER')
        elif content_type == 'pronunciation':
            checklist = LANGUAGES.get(self.language_code).get('PRONUNCIATION_HEADER')
        elif content_type == 'definitions':
            checklist = LANGUAGES.get(self.language_code).get('PARTS_OF_SPEECH')
            if self.language == 'chinese':
                checklist += self.current_word
        elif content_type == 'related':
            checklist = LANGUAGES.get(self.language_code).get('RELATIONS')
        else:
            return None
        # Early exit
        if not checklist:
            return []
        pruned_id_list = []
        if len(id_list) == 0:
            return []
        for item in id_list:
            text_to_check = item[2]
            if text_to_check in checklist or self.get_first_word(text_to_check) in checklist:
                pruned_id_list.append(item)
        return pruned_id_list

    def get_word_data(self, language):
        contents = self.soup.find_all('span', {'class': 'toctext'})
        start_index = None
        for content in contents:
            if content.text.lower() == language:
                start_index = content.find_previous().text + '.'
        if len(contents) != 0 and not start_index:
            for content in contents:
                if language in content.text.lower():
                    start_index = content.find_previous().text + '.'
        if len(contents) != 0 and not start_index:
            return []
        id_list = []
        included_items = self.get_included_items()
        for content in contents:
            index = content.find_previous().text
            content_text = self.remove_digits(content.text).strip().lower()
            if index.startswith(start_index) and \
                    (content_text in included_items or self.get_first_word(content_text) in included_items):
                content_id = content.parent['href'].replace('#', '')
                id_list.append((index, content_id, content_text))
        # if there's not a TOC
        if len(id_list) == 0:
            id_list = self.get_id_list_without_toc(language)
        word_data = {
            'examples': self.parse_examples(id_list),
            'definitions': self.parse_definitions(id_list),
            'etymologies': self.parse_etymologies(id_list),
            'related': self.parse_related_words(id_list),
            'pronunciations': self.parse_pronunciations(id_list),
        }
        json_obj_list = self.map_to_object(word_data)
        return json_obj_list

    def get_id_list_without_toc(self, language):
        id_list = []
        included_items = self.get_included_items()
        count = 1
        # Want to check each header that it has a word we're looking for and its parent has the language we're looking for
        parent_tag = ['h1']
        for htag in ['h2', 'h3', 'h4', 'h5']:
            hs = self.soup.find_all(htag)
            for h in hs:
                text = get_first_letter_seq(h.text)
                if text and text.lower() in included_items and prev_sib_contains(h, parent_tag, language):
                    span_id = self.get_span_id(h)
                    if span_id:
                        id_list.append((str(count), span_id, text.lower()))
                        count += 1
            if len(id_list) > 0:
                break
            parent_tag.append(htag)
        return id_list

    def get_span_id(self, elem):
        for span in elem.find_all('span'):
            if span.text == elem.text:
                return span['id']

    def parse_pronunciations(self, word_contents):
        pronunciation_id_list = self.get_id_list(word_contents, 'pronunciation')
        pronunciation_list = []
        audio_links = []
        pronunciation_text = []
        pronunciation_div_classes = ['mw-collapsible', 'vsSwitcher']
        for pronunciation_index, pronunciation_id, _ in pronunciation_id_list:
            span_tag = self.soup.find_all('span', {'id': pronunciation_id})[0]
            list_tag = span_tag.parent
            while list_tag.name != 'ul':
                list_tag = list_tag.find_next_sibling()
                if list_tag.name == 'p':
                    pronunciation_text.append(list_tag.text)
                    break
                if list_tag.name == 'div' and any(_ in pronunciation_div_classes for _ in list_tag['class']):
                    break
            for super_tag in list_tag.find_all('sup'):
                super_tag.clear()
            for list_element in list_tag.find_all('li'):
                for audio_tag in list_element.find_all('div', {'class': 'mediaContainer'}):
                    audio_links.append(audio_tag.find('source')['src'])
                    audio_tag.extract()
                for nested_list_element in list_element.find_all('ul'):
                    nested_list_element.extract()
                if list_element.text and not list_element.find('table', {'class': 'audiotable'}):
                    pronunciation_text.append(list_element.text.strip())
            pronunciation_list.append((pronunciation_index, pronunciation_text, audio_links))
        return pronunciation_list

    def parse_definitions(self, word_contents):
        definition_id_list = self.get_id_list(word_contents, 'definitions')
        definition_list = []
        definition_tag = None
        for def_index, def_id, def_type in definition_id_list:
            definition_text = []
            span_tag = self.soup.find_all('span', {'id': def_id})[0]
            table = span_tag.parent.find_next_sibling()
            while table and table.name not in ['h2', 'h3', 'h4', 'h5']:
                definition_tag = table
                table = table.find_next_sibling()
                if definition_tag.name == 'p':
                    definition_text.append(definition_tag.text.strip())
                if definition_tag.name in ['ol', 'ul']:
                    for element in definition_tag.find_all('li', recursive=False):
                        if element.text:
                            definition_text.append(element.text.strip())
                if definition_tag.name == 'dl':
                    for element in definition_tag.find_all('dd', recursive=False):
                        text = self.get_text_except_elements(element, ['style'])
                        # Sometimes in Spanish, the definitions have examples or synonyms below them.
                        # This gets all the text from the beginning up to the first <ul> element.
                        if text and element.ul and element.ul.text:
                            text = text.split(element.ul.text, 1)[0]
                        definition_text.append(text.strip())
            if def_type == 'definitions':
                def_type = ''
            definition_list.append((def_index, definition_text, def_type))
        return definition_list

    def get_text_except_elements(self, tag, elements_to_remove):
        text = tag.text
        for element in elements_to_remove:
            for e in tag.find_all(element, recursive=False):
                if e.text:
                    text = text.replace(e.text, '')
        return text

    def parse_examples(self, word_contents):
        definition_id_list = self.get_id_list(word_contents, 'definitions')
        example_list = []
        for def_index, def_id, def_type in definition_id_list:
            span_tag = self.soup.find_all('span', {'id': def_id})[0]
            table = span_tag.parent
            while table and table.name != 'ol':
                table = table.find_next_sibling()
            examples = []
            while table and table.name == 'ol':
                for element in table.find_all('dd'):
                    example_text = re.sub(r'\([^)]*\)', '', element.text.strip())
                    if example_text:
                        examples.append(example_text)
                    element.clear()
                example_list.append((def_index, examples, def_type))
                for quot_list in table.find_all(['ul', 'ol']):
                    quot_list.clear()
                table = table.find_next_sibling()
        return example_list

    def parse_etymologies(self, word_contents):
        etymology_id_list = self.get_id_list(word_contents, 'etymologies')
        etymology_list = []
        etymology_tag = None
        for etymology_index, etymology_id, _ in etymology_id_list:
            etymology_text = ''
            span_tag = self.soup.find_all('span', {'id': etymology_id})[0]
            next_tag = span_tag.parent.find_next_sibling()
            while next_tag.name not in ['h3', 'h4', 'div', 'h5']:
                etymology_tag = next_tag
                next_tag = next_tag.find_next_sibling()
                if etymology_tag.name == 'p':
                    etymology_text += etymology_tag.text
                else:
                    for list_tag in etymology_tag.find_all('li'):
                        etymology_text += list_tag.text + '\n'
            etymology_list.append((etymology_index, etymology_text))
        return etymology_list

    def parse_related_words(self, word_contents):
        relation_id_list = self.get_id_list(word_contents, 'related')
        related_words_list = []
        for related_index, related_id, relation_type in relation_id_list:
            words = []
            span_tag = self.soup.find_all('span', {'id': related_id})[0]
            parent_tag = span_tag.parent
            while not parent_tag.find_all('li'):
                parent_tag = parent_tag.find_next_sibling()
            for list_tag in parent_tag.find_all('li'):
                words.append(list_tag.text)
            related_words_list.append((related_index, words, relation_type))
        return related_words_list

    def map_to_object(self, word_data):
        json_obj_list = []
        if not word_data['etymologies']:
            word_data['etymologies'] = [('', '')]
        for (current_etymology, next_etymology) in zip_longest(word_data['etymologies'], word_data['etymologies'][1:], fillvalue=('999', '')):
            data_obj = WordData()
            data_obj.etymology = current_etymology[1]
            for pronunciation_index, text, audio_links in word_data['pronunciations']:
                if (self.count_digits(current_etymology[0]) == self.count_digits(pronunciation_index)) or (current_etymology[0] <= pronunciation_index < next_etymology[0]):
                    data_obj.pronunciations = text
                    data_obj.audio_links = audio_links
            for definition_index, definition_text, definition_type in word_data['definitions']:
                if current_etymology[0] <= definition_index < next_etymology[0]:
                    def_obj = Definition()
                    def_obj.text = definition_text
                    def_obj.part_of_speech = definition_type
                    for example_index, examples, _ in word_data['examples']:
                        if example_index.startswith(definition_index):
                            def_obj.example_uses = examples
                    for related_word_index, related_words, relation_type in word_data['related']:
                        if related_word_index.startswith(definition_index):
                            def_obj.related_words.append(RelatedWord(relation_type, related_words))
                    data_obj.definition_list.append(def_obj)
            json_obj_list.append(data_obj.to_json())
        return json_obj_list

    def fetch(self, word, language=None, old_id=None):
        language = self.language if not language else language
        response = self.session.get(self.url.format(word), params={'oldid': old_id})

        self.soup = BeautifulSoup(response.text.replace('>\n<', '><'), 'html.parser')
        self.current_word = word
        self.clean_html()
        return self.get_word_data(language.lower())


def get_first_letter_seq(text):
    if not text:
        return None
    # must use \W so letters with accents are also matched
    # this splits on any non-letter and any digit, so all that's left is groups of letters
    tks = re.split("[\W0-9_]", text)
    for t in tks:
        if t:
            return t
    return None


# Checks if there is a text match with the previous sibling's text.
def prev_sib_contains(elem, tags_to_match, text):
    sib = elem.find_previous_sibling(tags_to_match)
    if sib.text and text in sib.text.lower():
        return True
    return False
