import uos
import gc


class Storage:
    # ユーザー情報のキーを定数として定義
    USER_KEYS = [
        "usr_name", "usr_name_kana", "usr_gender", "usr_birthday",
        "usr_age", "usr_addr", "usr_phone",
        "usr_mobile", "usr_email", "usr_family", "usr_licenses",
        "usr_siboudouki", "usr_hobby", "usr_skill", "usr_access"
    ]

    # 改行をBRタグに置換するキーのセット
    KEYS_TO_REPLACE = {
        "usr_licenses",
        "usr_siboudouki",
        "usr_hobby",
        "usr_skill",
        "job_description",
        "portrait_summary",
    }
    SIMPLEHIST_FIELDS = ("hist_no", "hist_datetime",
                         "hist_status", "hist_name")
    JOBHIST_FIELDS = ("job_no", "job_name", "job_description")
    PORTRAIT_FIELDS = ("portrait_no", "portrait_url", "portrait_summary")

    def __init__(self):
        self.data_dir = "/data"
        self.user_file = f"{self.data_dir}/user.csv"
        self.simplehist_file = f"{self.data_dir}/simplehist.csv"
        self.jobhist_file = f"{self.data_dir}/jobhist.csv"
        self.portrait_file = f"{self.data_dir}/portrait.csv"
        try:
            uos.mkdir(self.data_dir)
        except OSError:
            pass

    def read_user(self):
        try:
            with open(self.user_file, "r") as f:
                line = f.readline()
                if not line:
                    return {}
                values = line.strip().split(",")
                # <br> を \n に戻す
                decoded_values = [v.replace("<br>", "\n") for v in values]
                return dict(zip(self.USER_KEYS, decoded_values))
        except OSError:
            return {}

    def write_user(self, data):
        record = self._build_record(data, self.USER_KEYS)
        self._safe_write_lines(
            self.user_file, [self._join_record(self.USER_KEYS, record)])

    def read_simplehist(self):
        return self._read_csv_with_fields(
            self.simplehist_file,
            self.SIMPLEHIST_FIELDS
        )

    def write_simplehist(self, data):
        gc.collect()
        self._write_csv_records(self.simplehist_file,
                                data, self.SIMPLEHIST_FIELDS)

    def _read_csv_with_fields(self, filepath, field_names):
        """
        CSV ファイルを読み込む共通メソッド
        field_names: フィールド名のタプル (例: ("job_no", "job_name", "job_description"))
        """
        try:
            with open(filepath, "r") as file:
                result = []
                while True:
                    line = file.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        # 最後のフィールドにカンマが含まれることを想定
                        values = line.split(",", len(field_names) - 1)
                        entry = {}
                        for i, field in enumerate(field_names):
                            if i < len(values):
                                val = values[i].replace("<br>", "\n")
                                if field.endswith("_no"):
                                    try:
                                        entry[field] = int(val)
                                    except ValueError:
                                        entry[field] = 0
                                else:
                                    entry[field] = val
                            else:
                                entry[field] = ""
                        result.append(entry)
                    del line
                return result
        except OSError:
            return []

    def read_jobhist(self):
        return self._read_csv_with_fields(
            self.jobhist_file,
            self.JOBHIST_FIELDS
        )

    def write_jobhist(self, data):
        if not data:
            return

        gc.collect()
        self._write_csv_records(self.jobhist_file, data, self.JOBHIST_FIELDS)

    def read_portrait(self):
        return self._read_csv_with_fields(
            self.portrait_file,
            self.PORTRAIT_FIELDS
        )

    def write_portrait(self, data):
        gc.collect()
        self._write_csv_records(self.portrait_file, data, self.PORTRAIT_FIELDS)

    def _safe_write_lines(self, filepath, lines):
        temp_path = filepath + ".tmp"
        try:
            with open(temp_path, "w") as file:
                first = True
                for line in lines:
                    if not first:
                        file.write("\n")
                    file.write(line)
                    first = False
            try:
                uos.remove(filepath)
            except OSError:
                pass
            uos.rename(temp_path, filepath)
        except Exception:
            try:
                uos.remove(temp_path)
            except OSError:
                pass
            raise

    def _write_csv_records(self, filepath, data, field_names):
        def iter_lines():
            for entry in data:
                record = self._build_record(entry, field_names)
                yield self._join_record(field_names, record)

        self._safe_write_lines(filepath, iter_lines())

    def _build_record(self, data, field_names):
        record = {}
        for field in field_names:
            record[field] = self._sanitize_value(field, data.get(field, ""))
        return record

    def _join_record(self, field_names, record):
        values = []
        for field in field_names:
            values.append(self._escape_csv_value(record.get(field, "")))
        return ",".join(values)

    def _escape_csv_value(self, value):
        return str(value).replace(",", "、")

    def _sanitize_value(self, key, value):
        if value is None:
            return ""
        if key in self.KEYS_TO_REPLACE:
            return value.replace("\n", "<br>")
        return value
