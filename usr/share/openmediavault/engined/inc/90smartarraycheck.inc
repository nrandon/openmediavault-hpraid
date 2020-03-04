<?php
/**
 * @license   http://www.gnu.org/licenses/gpl.html GPL Version 3
 * @copyright Copyright (c) 2013-2022 OpenMediaVault Plugin Developers
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */
 require_once("openmediavault/functions.inc");

\OMV\System\LogFileSpec::registerSpecification("smartarraycheck", [
    "filename" => "smart-array-check.log",
    "filepath" => "/var/log/smartarraycheck/smart-array-check.log",
    "regex"    => "/^(\S+\s\S+),\d+\s(\[.*\])\s(\S+)\s+(\d+)\s+(\S+)\s+(.*)$/",
    "columns"  => [
        "date"  => [
            "index" => 1,
            "func"  => function($v) {
                return strftime("%c", strtotime($v));
            }
        ],
        "threadName" => 2,
        "filename"   => 3,
        "lineNo"     => 4,
        "levelName"  => 5,
        "message"    => 6
     ]
]);
